(* Context entries, class tables, name resolution, predefined modules *)
theory Contexts
  imports Syntax "HOL-Library.List_Lexorder" "HOL-Library.Char_ord"
begin

(* Possibly unassigned entries carry a flag, set when the variable is declared in a branch, for the diagnostic
   only *)
datatype cxt_entry =
    Ty ty
  | DU ty
  | PU ty bool
  | Unbound
  | ModStub name
  | ModChecked name "(var, cxt_entry) fmap"
  | TypeAlias "(var, cxt_entry) fmap" name "type_def located list" nat
  | Type name
  | TypeVar
  | Scheme ty_scheme
  | PUScheme ty_scheme bool
  | PredefName

type_synonym cxt = "(var, cxt_entry) fmap"

datatype class_entry = ClassDef cxt name "type_def located list" nat

type_synonym class_table = "(name, class_entry) fmap"

fun lookup :: "cxt \<Rightarrow> name \<Rightarrow> cxt_entry option"
where
"lookup \<Gamma> (x, []) = fmlookup \<Gamma> x" |
"lookup \<Gamma> (x, y # ys) = (case fmlookup \<Gamma> x of Some (ModChecked _ \<Gamma>') \<Rightarrow> lookup \<Gamma>' (y, ys) | _ \<Rightarrow> None)"

definition resolve_name :: "cxt \<Rightarrow> name \<Rightarrow> cxt_entry option"
where
"resolve_name \<Gamma> q =
  (case lookup \<Gamma> q of
     Some (Ty \<tau>) \<Rightarrow> Some (Ty \<tau>)
   | Some (ModChecked q' \<Gamma>') \<Rightarrow> Some (ModChecked q' \<Gamma>')
   | Some (Type C) \<Rightarrow> Some (Type C)
   | Some (TypeAlias \<Gamma>' q' \<chi>s i) \<Rightarrow> Some (TypeAlias \<Gamma>' q' \<chi>s i)
   | Some (Scheme \<pi>) \<Rightarrow> Some (Scheme \<pi>)
   | Some PredefName \<Rightarrow> Some PredefName
   | _ \<Rightarrow> None)"

definition range_class :: name where "range_class = snoc builtins (var ''range'')"

abbreviation name_binding :: "var \<times> cxt_entry"
where "name_binding \<equiv> (var ''__name__'', Ty (TyPrim str))"

definition predefined :: "(name, cxt) fmap"
where
"predefined = fmap_of_list
  [(builtins, fmap_of_list
     ([name_binding,
       (var ''print'', Ty (TyCallable [TyPrim object] (TyPrim NoneType))),
       (var ''len'', Ty (TyCallable [TyPrim Sized] (TyPrim int))),
       (var ''range'', Type range_class),
       (var ''round'', Ty (TyCallable [TyPrim float] (TyPrim int)))]
      @ map (\<lambda>\<nu>. (prim_name \<nu>, PredefName)) [NoneType, object, bool, int, float, str]
      @ map (\<lambda>x. (var x, PredefName)) [''list'', ''dict'', ''tuple''])),
   ((var ''sys'', []), fmap_of_list
     [name_binding, (var ''argv'', Ty (TyList (TyPrim str))),
      (var ''exit'', Ty (TyCallable [TyPrim int] (TyPrim Never)))]),
   ((var ''typing'', []), fmap_of_list
     [name_binding, (var ''Callable'', PredefName), (var ''Literal'', PredefName),
      (prim_name Never, PredefName), (prim_name Sized, PredefName)]),
   ((var ''dataclasses'', []),
    fmap_of_list [name_binding, (var ''dataclass'', PredefName)])]"

(* Boxed plus of the specification isn't in Isabelle's symbol table *)
function (sequential) extend_entry :: "cxt_entry \<Rightarrow> cxt_entry \<Rightarrow> cxt_entry"
and extend :: "cxt \<Rightarrow> cxt \<Rightarrow> cxt" (infixl "\<uplus>" 65)
where
"extend_entry (ModChecked q \<Gamma>) (ModStub q') = (if q = q' then ModChecked q \<Gamma> else ModStub q')" |
"extend_entry (ModChecked q \<Gamma>) (ModChecked q' \<Gamma>') =
   (if q = q' then ModChecked q (\<Gamma> \<uplus> \<Gamma>') else ModChecked q' \<Gamma>')" |
"extend_entry _ \<theta>' = \<theta>'" |
"\<Gamma> \<uplus> \<Gamma>' =
   \<Gamma> ++\<^sub>f fmmap_keys (\<lambda>x \<theta>'. case fmlookup \<Gamma> x of None \<Rightarrow> \<theta>' | Some \<theta> \<Rightarrow> extend_entry \<theta> \<theta>') \<Gamma>'"
by pat_completeness auto

termination
by (relation "measure (\<lambda>p. case p of Inl (\<theta>, _) \<Rightarrow> size \<theta> | Inr (\<Gamma>, _) \<Rightarrow> size_fmap (\<lambda>_. 0) size \<Gamma>)")
   (simp_all add: size_fmap_lookup del: size_fmap_def)

definition predefined_classes :: class_table
where
"predefined_classes =
  fmupd range_class
    (ClassDef (the (fmlookup predefined builtins)) builtins
      [At no_pos (Dataclass (var ''range'') [] None
        [(var ''start'', TyExprPrim int), (var ''stop'', TyExprPrim int)])] 0)
    fmempty"

lemma sorted_list_of_fmap_lookup: "(k, v) \<in> set (sorted_list_of_fmap m) \<Longrightarrow> fmlookup m k = Some v"
  unfolding sorted_list_of_fmap_def by (auto simp: fmlookup_dom_iff)

(* Alias definitions reachable from a context, through the contexts of its aliases and checked modules *)
function (sequential) entry_aliases :: "cxt_entry \<Rightarrow> nat" and aliases :: "cxt \<Rightarrow> nat"
where
"entry_aliases (TypeAlias \<Gamma> _ \<chi>s _) =
  length (filter (\<lambda>\<chi>. case node \<chi> of TypeStmt _ _ _ \<Rightarrow> True | _ \<Rightarrow> False) \<chi>s) + aliases \<Gamma>" |
"entry_aliases (ModChecked _ \<Gamma>) = aliases \<Gamma>" |
"entry_aliases _ = 0" |
"aliases \<Gamma> = sum_list (map (entry_aliases \<circ> snd) (sorted_list_of_fmap \<Gamma>))"
by pat_completeness auto

termination
by (relation "measure (\<lambda>p. case p of Inl \<theta> \<Rightarrow> size \<theta> | Inr \<Gamma> \<Rightarrow> size_fmap (\<lambda>_. 0) size \<Gamma>)")
   (auto dest!: sorted_list_of_fmap_lookup simp: size_fmap_lookup simp del: size_fmap_def)

definition entry_of :: "cxt \<Rightarrow> expr \<Rightarrow> cxt_entry option"
where
"entry_of \<Gamma> e = Option.bind (dotted_name e) (resolve_name \<Gamma>)"

definition class_of_name :: "cxt \<Rightarrow> expr \<Rightarrow> name option"
where
"class_of_name \<Gamma> e = (case entry_of \<Gamma> e of Some (Type C) \<Rightarrow> Some C | _ \<Rightarrow> None)"

definition scheme_of_name :: "cxt \<Rightarrow> expr \<Rightarrow> ty_scheme option"
where
"scheme_of_name \<Gamma> e = (case entry_of \<Gamma> e of Some (Scheme \<pi>) \<Rightarrow> Some \<pi> | _ \<Rightarrow> None)"

end
