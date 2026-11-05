(* Pattern checking; matched and remaining types of patterns *)
theory Patterns
  imports Subtyping
begin

definition check_pattern_class :: "cxt \<Rightarrow> name \<Rightarrow> name may_fail"
where
"check_pattern_class \<Gamma> q =
  (case resolve_name \<Gamma> q of
     Some (Type C) \<Rightarrow> if C = range_class then Fail RangePattern else Ok C
   | _ \<Rightarrow> Fail (NotClass q))"

definition pattern_class :: "cxt \<Rightarrow> name \<Rightarrow> name"
where
"pattern_class \<Gamma> q = (case resolve_name \<Gamma> q of Some (Type C) \<Rightarrow> C | _ \<Rightarrow> undefined)"

(* Sub-patterns of a constructor pattern for class C with arguments a, in the order of the fields of C *)
fun field_patterns :: "class_table \<Rightarrow> name \<Rightarrow> pat located args \<Rightarrow> pat located list"
where
"field_patterns \<Sigma> C (ps, kps) =
  ps @ concat (map (\<lambda>x. [p. (y, p) \<leftarrow> kps, y = x]) (drop (length ps) (field_names \<Sigma> C)))"

lemma field_patterns_elem: "p \<in> set (field_patterns \<Sigma> C (ps, kps)) \<Longrightarrow> p \<in> set ps \<or> p \<in> set (map snd kps)"
  by (auto simp: image_iff) (metis snd_conv)

fun disjuncts :: "ty \<Rightarrow> ty list"
where
"disjuncts (TyUnion \<sigma> \<tau>) = disjuncts \<sigma> @ disjuncts \<tau>" |
"disjuncts \<tau> = [\<tau>]"

fun has_values :: "class_table \<Rightarrow> sequence_kind \<Rightarrow> ty \<Rightarrow> bool"
where
"has_values \<Sigma> k (TyUnion \<sigma> \<tau>) = (has_values \<Sigma> k \<sigma> \<or> has_values \<Sigma> k \<tau>)" |
"has_values \<Sigma> k (TyVar _) = True" |
"has_values \<Sigma> TupleKind (TyTuple _) = True" |
"has_values \<Sigma> ListKind (TyList _) = True" |
"has_values \<Sigma> TupleKind \<tau> = (\<Sigma> \<turnstile> TyTuple [] <: \<tau>)" |
"has_values \<Sigma> ListKind \<tau> = (\<Sigma> \<turnstile> TyList (TyPrim object) <: \<tau>)" |
"has_values \<Sigma> RangeKind \<tau> = (\<Sigma> \<turnstile> TyClass range_class [] <: \<tau>)"

function (sequential) matched_as :: "class_table \<Rightarrow> cxt \<Rightarrow> ty \<Rightarrow> pat \<Rightarrow> ty"
where
"matched_as \<Sigma> \<Gamma> (TyUnion \<sigma> \<tau>) p = matched_as \<Sigma> \<Gamma> \<sigma> p \<squnion>\<^bsub>\<Sigma>\<^esub> matched_as \<Sigma> \<Gamma> \<tau> p" |
"matched_as \<Sigma> \<Gamma> \<tau> (PatVar _) = \<tau>" |
"matched_as \<Sigma> \<Gamma> \<tau> PatWildcard = \<tau>" |
"matched_as \<Sigma> \<Gamma> \<tau> (PatAs p _) = matched_as \<Sigma> \<Gamma> \<tau> (node p)" |
"matched_as \<Sigma> \<Gamma> \<tau> (PatLiteral (LitFloat _)) = meet \<Sigma> (TyPrim float) \<tau>" |
"matched_as \<Sigma> \<Gamma> \<tau> (PatLiteral l) = meet \<Sigma> (TyLiteral l) \<tau>" |
"matched_as \<Sigma> \<Gamma> (TyTuple \<tau>s) (PatTuple ps) =
  (if length \<tau>s = length ps then TyTuple (map2 (\<lambda>\<tau> p. matched_as \<Sigma> \<Gamma> \<tau> (node p)) \<tau>s ps)
   else TyPrim Never)" |
"matched_as \<Sigma> \<Gamma> (TyList \<tau>) (PatList _) = TyList \<tau>" |
"matched_as \<Sigma> \<Gamma> (TyDict \<tau>) (PatDict _) = TyDict \<tau>" |
"matched_as \<Sigma> \<Gamma> \<tau> (PatConstr q _) =
  (let C = pattern_class \<Gamma> q in
   case instance_at \<Sigma> C \<tau> of Instance \<sigma>s \<Rightarrow> meet \<Sigma> \<tau> (TyClass C \<sigma>s) | _ \<Rightarrow> TyPrim Never)" |
"matched_as \<Sigma> \<Gamma> _ _ = TyPrim Never"
by pat_completeness auto

termination
by (relation "measures [\<lambda>(_, _, _, p). size p, \<lambda>(_, _, \<tau>, _). size \<tau>]")
   (auto elim!: in_set_zipE dest: size_node_elem)

function (sequential) remaining :: "class_table \<Rightarrow> cxt \<Rightarrow> ty \<Rightarrow> pat \<Rightarrow> ty"
where
"remaining \<Sigma> \<Gamma> (TyUnion \<sigma> \<tau>) p = remaining \<Sigma> \<Gamma> \<sigma> p \<squnion>\<^bsub>\<Sigma>\<^esub> remaining \<Sigma> \<Gamma> \<tau> p" |
"remaining \<Sigma> \<Gamma> \<tau> (PatVar _) = TyPrim Never" |
"remaining \<Sigma> \<Gamma> \<tau> PatWildcard = TyPrim Never" |
"remaining \<Sigma> \<Gamma> \<tau> (PatAs p _) = remaining \<Sigma> \<Gamma> \<tau> (node p)" |
"remaining \<Sigma> \<Gamma> (TyLiteral l') (PatLiteral l) = (if l' = l then TyPrim Never else TyLiteral l')" |
"remaining \<Sigma> \<Gamma> (TyPrim bool) (PatLiteral (LitBool b)) = TyLiteral (LitBool (\<not> b))" |
"remaining \<Sigma> \<Gamma> (TyPrim NoneType) (PatLiteral LitNone) = TyPrim Never" |
"remaining \<Sigma> \<Gamma> (TyTuple \<tau>s) (PatTuple ps) =
  (if length \<tau>s = length ps then
     (let \<rho>s = map2 (\<lambda>\<tau> p. remaining \<Sigma> \<Gamma> \<tau> (node p)) \<tau>s ps in
      case filter (\<lambda>i. \<rho>s ! i \<noteq> TyPrim Never) [0..<length \<rho>s] of
        [] \<Rightarrow> TyPrim Never
      | [i] \<Rightarrow> TyTuple (\<tau>s[i := \<rho>s ! i])
      | _ \<Rightarrow> TyTuple \<tau>s)
   else TyTuple \<tau>s)" |
"remaining \<Sigma> \<Gamma> (TyDict _) (PatDict []) = TyPrim Never" |
"remaining \<Sigma> \<Gamma> \<tau> (PatConstr q a) =
  (let C = pattern_class \<Gamma> q in
   case instance_at \<Sigma> C \<tau> of
     Instance \<sigma>s \<Rightarrow>
       if \<Sigma> \<turnstile> \<tau> <: TyClass C \<sigma>s
          \<and> (\<forall>(p, \<sigma>) \<in> set (zip (field_patterns \<Sigma> C a) (field_types \<Sigma> C \<sigma>s)).
               remaining \<Sigma> \<Gamma> \<sigma> (node p) = TyPrim Never)
       then TyPrim Never
       else \<tau>
   | _ \<Rightarrow> \<tau>)" |
"remaining \<Sigma> \<Gamma> \<tau> _ = \<tau>"
by pat_completeness auto

termination
by (relation "measures [\<lambda>(_, _, _, p). size p, \<lambda>(_, _, \<tau>, _). size \<tau>]")
   (auto elim!: in_set_zipE dest!: field_patterns_elem
     dest: size_node_elem size_node_snd_elem')

definition check_unbound :: "cxt \<Rightarrow> var \<Rightarrow> unit may_fail"
where
"check_unbound \<Gamma> x = ensure (fmlookup \<Gamma> x = Some Unbound) (Redeclaration x)"

(* Bindings of pattern p at a type, joined from ms, the bindings at each disjunct. An entry None in ms means
   that p can't match that disjunct, and binds each variable of p at Never. *)
definition bindings_at :: "class_table \<Rightarrow> pat \<Rightarrow> (var, ty) fmap may_fail option list \<Rightarrow> (var, ty) fmap may_fail"
where
"bindings_at \<Sigma> p ms = do {
   \<Delta>s \<leftarrow> those_sum (map (\<lambda>m. case m of Some m' \<Rightarrow> m' | None \<Rightarrow> Ok (fmconst (binds p) (TyPrim Never))) ms);
   Ok (fmmap_keys (\<lambda>x _. joins \<Sigma> (map (\<lambda>\<Delta>. the (fmlookup \<Delta> x)) \<Delta>s)) (hd \<Delta>s))
 }"

(* Disjoint union of the bindings of sub-patterns *)
definition pattern_bindings :: "(var, ty) fmap may_fail list \<Rightarrow> (var, ty) fmap may_fail"
where
"pattern_bindings ms = do { \<Delta>s \<leftarrow> those_sum ms; Ok (fold (\<otimes>) \<Delta>s fmempty) }"

function
  check_pat :: "class_table \<Rightarrow> cxt \<Rightarrow> pat \<Rightarrow> ty \<Rightarrow> (var, ty) fmap may_fail" and
  check_pat_at :: "class_table \<Rightarrow> cxt \<Rightarrow> pat located \<Rightarrow> ty \<Rightarrow> (var, ty) fmap may_fail"
where
"check_pat \<Sigma> \<Gamma> PatWildcard \<tau> = Ok fmempty" |
"check_pat \<Sigma> \<Gamma> (PatVar x) \<tau> = do { check_unbound \<Gamma> x; Ok (fmupd x \<tau> fmempty) }" |
"check_pat \<Sigma> \<Gamma> (PatAs p x) \<tau> =
  do {
    check_unbound \<Gamma> x; \<Delta> \<leftarrow> check_pat_at \<Sigma> \<Gamma> p \<tau>;
    Ok (\<Delta> \<otimes> fmupd x (matched_as \<Sigma> \<Gamma> \<tau> (node p)) fmempty)
  }" |
"check_pat \<Sigma> \<Gamma> (PatLiteral _) \<tau> = Ok fmempty" |
"check_pat \<Sigma> \<Gamma> (PatTuple ps) \<tau> = do {
   ensure (\<not> has_values \<Sigma> ListKind \<tau>) (SequenceKindMismatch TupleKind \<tau> ListKind);
   ensure (\<not> has_values \<Sigma> RangeKind \<tau>) (SequenceKindMismatch TupleKind \<tau> RangeKind);
   bindings_at \<Sigma> (PatTuple ps)
     (map (\<lambda>\<sigma>. case \<sigma> of
                 TyTuple \<sigma>s \<Rightarrow>
                   if length \<sigma>s = length ps then Some (pattern_bindings (map2 (check_pat_at \<Sigma> \<Gamma>) ps \<sigma>s))
                   else None
               | _ \<Rightarrow> None)
       (disjuncts \<tau>))
 }" |
"check_pat \<Sigma> \<Gamma> (PatList ps) \<tau> = do {
   ensure (\<not> has_values \<Sigma> TupleKind \<tau>) (SequenceKindMismatch ListKind \<tau> TupleKind);
   ensure (\<not> has_values \<Sigma> RangeKind \<tau>) (SequenceKindMismatch ListKind \<tau> RangeKind);
   bindings_at \<Sigma> (PatList ps)
     (map (\<lambda>\<sigma>. case \<sigma> of
                 TyList \<sigma>' \<Rightarrow> Some (pattern_bindings (map (\<lambda>p. check_pat_at \<Sigma> \<Gamma> p \<sigma>') ps))
               | _ \<Rightarrow> None)
       (disjuncts \<tau>))
 }" |
"check_pat \<Sigma> \<Gamma> (PatDict kps) \<tau> =
  bindings_at \<Sigma> (PatDict kps)
    (map (\<lambda>\<sigma>. case \<sigma> of
                TyDict \<sigma>' \<Rightarrow> Some (pattern_bindings (map (\<lambda>p. check_pat_at \<Sigma> \<Gamma> p \<sigma>') (map snd kps)))
              | _ \<Rightarrow> None)
      (disjuncts \<tau>))" |
"check_pat \<Sigma> \<Gamma> (PatConstr q (ps, kps)) \<tau> = do {
   C \<leftarrow> check_pattern_class \<Gamma> q;
   check_field_map (PatternArityMismatch (short_name C)) (UnknownFieldInPattern (short_name C))
     (field_names \<Sigma> C) (length ps) (map fst kps);
   bindings_at \<Sigma> (PatConstr q (ps, kps))
     (map (\<lambda>\<sigma>. case instance_at \<Sigma> C \<sigma> of
                 Instance \<sigma>s \<Rightarrow>
                   Some (pattern_bindings
                     (map2 (check_pat_at \<Sigma> \<Gamma>) (field_patterns \<Sigma> C (ps, kps)) (field_types \<Sigma> C \<sigma>s)))
               | NoInstance \<Rightarrow> None
               | Undetermined \<Rightarrow> Some (Fail (PatternClassUndetermined (short_name C) \<sigma>)))
       (disjuncts \<tau>))
 }" |

"check_pat_at \<Sigma> \<Gamma> (At p q) \<tau> = locate p (check_pat \<Sigma> \<Gamma> q \<tau>)"
by pat_completeness auto

termination
by (relation "measure (\<lambda>x. case x of Inl (_, _, p, _) \<Rightarrow> size p | Inr (_, _, p, _) \<Rightarrow> size_located size p)")
   (auto elim!: in_set_zipE dest!: field_patterns_elem
     dest: size_node_elem size_node_snd_elem size_node_snd_elem'
     simp del: field_patterns.simps)

end
