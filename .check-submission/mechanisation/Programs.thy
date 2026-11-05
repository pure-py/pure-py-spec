(* Typing of imports, modules and programs *)
theory Programs
  imports Typing
begin

type_synonym program = "(name, module_body) fmap"

context includes fmap.lifting
begin
lift_definition submods :: "program \<Rightarrow> name \<Rightarrow> cxt"
  is "\<lambda>M q x. if snoc q x \<in> dom M then Some (ModStub (snoc q x)) else None"
proof -
  fix M :: "name \<Rightarrow> module_body option" and q
  let ?S = "\<lambda>x. if snoc q x \<in> dom M then Some (ModStub (snoc q x)) else None"
  assume "finite (dom M)"
  have "dom ?S \<subseteq> (\<lambda>q'. snd (the (unsnoc q'))) ` dom M"
    by (auto simp: dom_def image_iff intro: rev_image_eqI)
  then show "finite (dom ?S)"
    using \<open>finite (dom M)\<close> by (blast intro: finite_subset finite_imageI)
qed
end

lemma submods_of_list [code]:
  "submods (fmap_of_list m) q
   = fmap_of_list (map (\<lambda>(q', _). (snd (the (unsnoc q')), ModStub q'))
                       (filter (\<lambda>(q', _). case unsnoc q' of Some (q'', _) \<Rightarrow> q'' = q | None \<Rightarrow> False) m))"
proof (rule fmap_ext)
  fix x
  let ?l = "map (\<lambda>(q', _). (snd (the (unsnoc q')), ModStub q'))
              (filter (\<lambda>(q', _). case unsnoc q' of Some (q'', _) \<Rightarrow> q'' = q | None \<Rightarrow> False) m)"
  have "map_of ?l x = (if snoc q x \<in> dom (map_of m) then Some (ModStub (snoc q x)) else None)"
    by (induction m) (auto simp: dom_def snoc_eq_iff simp del: snoc.simps unsnoc.simps split: option.splits)
  then show "fmlookup (submods (fmap_of_list m) q) x = fmlookup (fmap_of_list ?l) x"
    by (simp add: submods.rep_eq fmlookup_of_list)
qed

(* Failure in module q located at p, unless already located *)
definition locate_in :: "name \<Rightarrow> pos \<Rightarrow> (name \<times> reason) + 'a \<Rightarrow> (name \<times> reason) + 'a"
where
"locate_in q p = map_sum (\<lambda>(q', r). (q', if q' = q then locate_reason p r else r)) id"

(* V holds the modules being checked, in order, so that an import cycle is rejected; failure paired
   with the module in which it occurs *)
function (sequential)
  check_module ::
    "program \<Rightarrow> name list \<Rightarrow> class_table \<Rightarrow> name \<Rightarrow> name \<Rightarrow> (name \<times> reason) + cxt \<times> class_table" and
  check_imports ::
    "program \<Rightarrow> name list \<Rightarrow> class_table \<Rightarrow> name \<Rightarrow> import located list
     \<Rightarrow> (name \<times> reason) + cxt \<times> class_table" and
  submodules ::
    "program \<Rightarrow> name list \<Rightarrow> class_table \<Rightarrow> name \<Rightarrow> name \<Rightarrow> cxt \<Rightarrow> var list
     \<Rightarrow> (name \<times> reason) + cxt \<times> class_table" and
  imports_entry ::
    "program \<Rightarrow> name list \<Rightarrow> class_table \<Rightarrow> name \<Rightarrow> name \<Rightarrow> cxt \<Rightarrow> var
     \<Rightarrow> (name \<times> reason) + cxt_entry \<times> class_table" and
  imports_entries ::
    "program \<Rightarrow> name list \<Rightarrow> class_table \<Rightarrow> name \<Rightarrow> name \<Rightarrow> cxt \<Rightarrow> var list
     \<Rightarrow> (name \<times> reason) + cxt_entry list \<times> class_table" and
  check_modules ::
    "program \<Rightarrow> name list \<Rightarrow> class_table \<Rightarrow> name \<Rightarrow> name list \<Rightarrow> (name \<times> reason) + class_table"
where
"check_module M V \<Sigma> q' q =
  (case fmlookup predefined q of
     Some \<Gamma> \<Rightarrow> Ok (\<Gamma>, \<Sigma>)
   | None \<Rightarrow>
     if q \<in> set V then Fail (q, ImportCycle (dropWhile (\<lambda>q''. q'' \<noteq> q) V @ [q]))
     else case fmlookup M q of
       None \<Rightarrow> Fail (q', UnknownModule q)
     | Some (ModuleBody \<iota>s t) \<Rightarrow> do {
         (\<Gamma>', \<Sigma>') \<leftarrow> check_imports M (V @ [q]) \<Sigma> q \<iota>s;
         map_sum (Pair q) id (do {
           (case redeclared node {} (declarations \<iota>s) of
              Some y \<Rightarrow> Fail (Located (pos_of y) (DuplicateImportedName (node y)))
            | None \<Rightarrow> Ok ());
           \<Gamma>\<^sub>s \<leftarrow>
             (case scope Unbound (declares \<iota>s) t of
                Some \<Gamma>\<^sub>s \<Rightarrow> Ok \<Gamma>\<^sub>s
              | None \<Rightarrow> Fail (redeclaration (declares \<iota>s) (declarations t) (pat_bound t)));
           check_assignments_declared {} (assign_targets t) (declares t) (binds t);
           (R, \<Sigma>'') \<leftarrow> check_top_stmt \<Sigma>' q (the (fmlookup predefined builtins) \<otimes> \<Gamma>' \<otimes> \<Gamma>\<^sub>s) t;
           case R of
             Assigns\<^sub>R \<Delta> _ \<Rightarrow>
               let S = submods M q; X = (fmdom \<Gamma>' |\<union>| fmdom \<Delta>) |\<inter>| fmdom S in
               if X = {||} then Ok (S \<otimes> \<Delta>, \<Sigma>'')
               else let x = Min (fset X) in Fail (Located (binder_pos \<iota>s t x) (DuplicateMember x q))
           | Returns\<^sub>R \<Rightarrow> Fail (Located (last_pos t) TopLevelAssertFalse)
         })
       })" |

"check_imports M V \<Sigma> q [] = Ok (fmempty, \<Sigma>)" |
"check_imports M V \<Sigma> q (At p (Import (x, xs)) # \<iota>s) = locate_in q p (do {
   ensure (\<not> q \<prec> (x, xs)) (q, ImportOfContainedModule (x, xs) q);
   (\<Delta>, \<Sigma>\<^sub>1) \<leftarrow> check_module M V \<Sigma> q (x, []);
   (\<Delta>', \<Sigma>\<^sub>2) \<leftarrow> submodules M V \<Sigma>\<^sub>1 q (x, []) \<Delta> xs;
   (\<Gamma>, \<Sigma>') \<leftarrow> check_imports M V \<Sigma>\<^sub>2 q \<iota>s;
   Ok (fmupd x (ModChecked (x, []) \<Delta>') fmempty \<uplus> \<Gamma>, \<Sigma>')
 })" |
"check_imports M V \<Sigma> q (At p (FromImport q' xs) # \<iota>s) = locate_in q p (do {
   (\<Delta>, \<Sigma>\<^sub>1) \<leftarrow> check_module M V \<Sigma> q q';
   \<Sigma>\<^sub>2 \<leftarrow> check_modules M V \<Sigma>\<^sub>1 q (unique_to q' q);
   (case redeclared id {} xs of Some x \<Rightarrow> Fail (q, DuplicateImportedName x) | None \<Rightarrow> Ok ());
   (\<theta>s, \<Sigma>\<^sub>3) \<leftarrow> imports_entries M V \<Sigma>\<^sub>2 q q' \<Delta> xs;
   (\<Gamma>, \<Sigma>') \<leftarrow> check_imports M V \<Sigma>\<^sub>3 q \<iota>s;
   Ok (fmap_of_list (zip xs \<theta>s) \<uplus> \<Gamma>, \<Sigma>')
 })" |

"submodules M V \<Sigma> q q' \<Gamma> [] = Ok (\<Gamma>, \<Sigma>)" |
"submodules M V \<Sigma> q q' \<Gamma> (x # xs) = do {
   (\<Delta>, \<Sigma>\<^sub>1) \<leftarrow> check_module M V \<Sigma> q (snoc q' x);
   (\<Delta>', \<Sigma>') \<leftarrow> submodules M V \<Sigma>\<^sub>1 q (snoc q' x) \<Delta> xs;
   Ok (\<Gamma> \<uplus> fmupd x (ModChecked (snoc q' x) \<Delta>') fmempty, \<Sigma>')
 }" |

"imports_entry M V \<Sigma> q q' \<Gamma> x =
  (case fmlookup \<Gamma> x of
     Some (ModStub q'') \<Rightarrow> do { (\<Gamma>', \<Sigma>') \<leftarrow> check_module M V \<Sigma> q q''; Ok (ModChecked q'' \<Gamma>', \<Sigma>') }
   | \<theta> \<Rightarrow>
       (case resolve_name \<Gamma> (x, []) of
          Some \<theta>' \<Rightarrow> Ok (\<theta>', \<Sigma>)
        | None \<Rightarrow> Fail (q, case \<theta> of None \<Rightarrow> UnknownMember x q' | Some _ \<Rightarrow> UnassignedMember x q')))" |

"imports_entries M V \<Sigma> q q' \<Gamma> [] = Ok ([], \<Sigma>)" |
"imports_entries M V \<Sigma> q q' \<Gamma> (x # xs) = do {
   (\<theta>, \<Sigma>\<^sub>1) \<leftarrow> imports_entry M V \<Sigma> q q' \<Gamma> x;
   (\<theta>s, \<Sigma>') \<leftarrow> imports_entries M V \<Sigma>\<^sub>1 q q' \<Gamma> xs;
   Ok (\<theta> # \<theta>s, \<Sigma>')
 }" |

"check_modules M V \<Sigma> q [] = Ok \<Sigma>" |
"check_modules M V \<Sigma> q (q' # qs) = do { (_, \<Sigma>\<^sub>1) \<leftarrow> check_module M V \<Sigma> q q'; check_modules M V \<Sigma>\<^sub>1 q qs }"
by pat_completeness auto
(* Measures: count of modules of M not in V; then a topological rank of the call graph, which is acyclic
   if we remove the call from the module rule to its imports; then the length of the list argument *)
termination
by (relation "measures [
     \<lambda>x. case x of
       Inl (Inl (M, V, _)) \<Rightarrow> card (fmdom' M - set V)
     | Inl (Inr (Inl (M, V, _))) \<Rightarrow> card (fmdom' M - set V)
     | Inl (Inr (Inr (M, V, _))) \<Rightarrow> card (fmdom' M - set V)
     | Inr (Inl (M, V, _)) \<Rightarrow> card (fmdom' M - set V)
     | Inr (Inr (Inl (M, V, _))) \<Rightarrow> card (fmdom' M - set V)
     | Inr (Inr (Inr (M, V, _))) \<Rightarrow> card (fmdom' M - set V),
     \<lambda>x. case x of
       Inl (Inl _) \<Rightarrow> 0
     | Inl (Inr (Inl _)) \<Rightarrow> 3
     | Inl (Inr (Inr _)) \<Rightarrow> 1
     | Inr (Inl _) \<Rightarrow> 1
     | Inr (Inr (Inl _)) \<Rightarrow> 2
     | Inr (Inr (Inr _)) \<Rightarrow> 1,
     \<lambda>x. case x of
       Inl (Inl _) \<Rightarrow> 0
     | Inl (Inr (Inl (_, _, _, _, \<iota>s))) \<Rightarrow> length \<iota>s
     | Inl (Inr (Inr (_, _, _, _, _, _, xs))) \<Rightarrow> length xs
     | Inr (Inl _) \<Rightarrow> 0
     | Inr (Inr (Inl (_, _, _, _, _, _, xs))) \<Rightarrow> length xs
     | Inr (Inr (Inr (_, _, _, _, qs))) \<Rightarrow> length qs]")
   (auto simp: card_fmdom_insert)

definition check_program :: "program \<Rightarrow> (name \<times> reason) option"
where
"check_program M =
  (case check_module M [] predefined_classes main main of Fail f \<Rightarrow> Some f | Ok _ \<Rightarrow> None)"

end
