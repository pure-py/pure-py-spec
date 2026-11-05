(* Subtyping, join and meet; element, subscript and attribute types *)
theory Subtyping
  imports Types
begin

inductive subty :: "class_table \<Rightarrow> ty \<Rightarrow> ty \<Rightarrow> bool" ("_ \<turnstile> _ <: _" [51, 51, 51] 50)
and subtys :: "class_table \<Rightarrow> ty list \<Rightarrow> ty list \<Rightarrow> bool" ("_ \<turnstile> _ [<:] _" [51, 51, 51] 50)
for \<Sigma> :: class_table
where
SubtyRefl: "\<Sigma> \<turnstile> \<tau> <: \<tau>" |
SubtyClassExtend:
  "\<lbrakk> base \<Sigma> C = Some (D, \<sigma>s) ; \<Sigma> \<turnstile> TyClass D (map (subst \<tau>s (type_params \<Sigma> C)) \<sigma>s) <: \<tau>' \<rbrakk>
  \<Longrightarrow> \<Sigma> \<turnstile> TyClass C \<tau>s <: \<tau>'" |
SubtyClass: "\<lbrakk> \<Sigma> \<turnstile> \<sigma>s [<:] \<tau>s ; \<Sigma> \<turnstile> \<tau>s [<:] \<sigma>s \<rbrakk> \<Longrightarrow> \<Sigma> \<turnstile> TyClass C \<sigma>s <: TyClass C \<tau>s" |
SubtyNever: "\<Sigma> \<turnstile> TyPrim Never <: \<tau>" |
SubtyObject: "\<Sigma> \<turnstile> \<tau> <: TyPrim object" |
SubtyIntFloat: "\<Sigma> \<turnstile> TyPrim int <: TyPrim float" |
SubtySized: "sized \<tau> \<Longrightarrow> \<Sigma> \<turnstile> \<tau> <: TyPrim Sized" |
SubtyList: "\<lbrakk> \<Sigma> \<turnstile> \<sigma> <: \<tau> ; \<Sigma> \<turnstile> \<tau> <: \<sigma> \<rbrakk> \<Longrightarrow> \<Sigma> \<turnstile> TyList \<sigma> <: TyList \<tau>" |
SubtyDict: "\<lbrakk> \<Sigma> \<turnstile> \<sigma> <: \<tau> ; \<Sigma> \<turnstile> \<tau> <: \<sigma> \<rbrakk> \<Longrightarrow> \<Sigma> \<turnstile> TyDict \<sigma> <: TyDict \<tau>" |
SubtyCallable:
  "\<lbrakk> \<Sigma> \<turnstile> \<tau>s [<:] \<sigma>s ; \<Sigma> \<turnstile> \<sigma> <: \<tau> \<rbrakk> \<Longrightarrow> \<Sigma> \<turnstile> TyCallable \<sigma>s \<sigma> <: TyCallable \<tau>s \<tau>" |
SubtyTuple: "\<Sigma> \<turnstile> \<sigma>s [<:] \<tau>s \<Longrightarrow> \<Sigma> \<turnstile> TyTuple \<sigma>s <: TyTuple \<tau>s" |
SubtyLiteral: "\<Sigma> \<turnstile> base_type_lit l <: \<tau> \<Longrightarrow> \<Sigma> \<turnstile> TyLiteral l <: \<tau>" |
SubtyUnionLeft: "\<Sigma> \<turnstile> \<sigma> <: \<tau> \<Longrightarrow> \<Sigma> \<turnstile> \<sigma> <: TyUnion \<tau> \<tau>'" |
SubtyUnionRight: "\<Sigma> \<turnstile> \<sigma> <: \<tau>' \<Longrightarrow> \<Sigma> \<turnstile> \<sigma> <: TyUnion \<tau> \<tau>'" |
SubtyUnion: "\<lbrakk> \<Sigma> \<turnstile> \<tau> <: \<sigma> ; \<Sigma> \<turnstile> \<tau>' <: \<sigma> \<rbrakk> \<Longrightarrow> \<Sigma> \<turnstile> TyUnion \<tau> \<tau>' <: \<sigma>" |

SubtysNil: "\<Sigma> \<turnstile> [] [<:] []" |
SubtysCons: "\<lbrakk> \<Sigma> \<turnstile> \<sigma> <: \<tau> ; \<Sigma> \<turnstile> \<sigma>s [<:] \<tau>s \<rbrakk> \<Longrightarrow> \<Sigma> \<turnstile> \<sigma> # \<sigma>s [<:] \<tau> # \<tau>s"

abbreviation equiv :: "class_table \<Rightarrow> ty \<Rightarrow> ty \<Rightarrow> bool" ("_ \<turnstile> _ \<approx> _" [51, 51, 51] 50)
where
"\<Sigma> \<turnstile> \<sigma> \<approx> \<tau> \<equiv> \<Sigma> \<turnstile> \<sigma> <: \<tau> \<and> \<Sigma> \<turnstile> \<tau> <: \<sigma>"

definition join :: "class_table \<Rightarrow> ty \<Rightarrow> ty \<Rightarrow> ty"
where
"join \<Sigma> \<sigma> \<tau> = (if \<Sigma> \<turnstile> \<sigma> <: \<tau> then \<tau> else if \<Sigma> \<turnstile> \<tau> <: \<sigma> then \<sigma> else TyUnion \<sigma> \<tau>)"

syntax "_join" :: "ty \<Rightarrow> class_table \<Rightarrow> ty \<Rightarrow> ty" ("_ \<squnion>\<^bsub>_\<^esub> _" [65, 0, 66] 65)
translations "\<sigma> \<squnion>\<^bsub>\<Sigma>\<^esub> \<tau>" \<rightleftharpoons> "CONST join \<Sigma> \<sigma> \<tau>"

definition joins :: "class_table \<Rightarrow> ty list \<Rightarrow> ty"
where
"joins \<Sigma> \<tau>s = foldr (\<lambda>\<sigma> \<tau>. \<sigma> \<squnion>\<^bsub>\<Sigma>\<^esub> \<tau>) \<tau>s (TyPrim Never)"

function (sequential)
  meet :: "class_table \<Rightarrow> ty \<Rightarrow> ty \<Rightarrow> ty" and
  meet_incomparable :: "class_table \<Rightarrow> ty \<Rightarrow> ty \<Rightarrow> ty"
where
"meet \<Sigma> \<sigma> \<tau> = (if \<Sigma> \<turnstile> \<sigma> <: \<tau> then \<sigma> else if \<Sigma> \<turnstile> \<tau> <: \<sigma> then \<tau> else meet_incomparable \<Sigma> \<sigma> \<tau>)" |

"meet_incomparable \<Sigma> (TyUnion \<sigma> \<sigma>') \<tau> = meet \<Sigma> \<sigma> \<tau> \<squnion>\<^bsub>\<Sigma>\<^esub> meet \<Sigma> \<sigma>' \<tau>" |
"meet_incomparable \<Sigma> \<sigma> (TyUnion \<tau> \<tau>') = meet \<Sigma> \<sigma> \<tau> \<squnion>\<^bsub>\<Sigma>\<^esub> meet \<Sigma> \<sigma> \<tau>'" |
"meet_incomparable \<Sigma> (TyCallable \<sigma>s \<sigma>) (TyCallable \<tau>s \<tau>) =
  (if length \<sigma>s = length \<tau>s then TyCallable (map2 (\<lambda>\<sigma>' \<tau>'. \<sigma>' \<squnion>\<^bsub>\<Sigma>\<^esub> \<tau>') \<sigma>s \<tau>s) (meet \<Sigma> \<sigma> \<tau>) else TyPrim Never)" |
"meet_incomparable \<Sigma> (TyTuple \<sigma>s) (TyTuple \<tau>s) =
  (if length \<sigma>s = length \<tau>s then TyTuple (map2 (meet \<Sigma>) \<sigma>s \<tau>s) else TyPrim Never)" |
"meet_incomparable \<Sigma> _ _ = TyPrim Never"
by pat_completeness auto

termination
by (relation "measures [
     \<lambda>x. case x of Inl (_, \<sigma>, \<tau>) \<Rightarrow> size \<sigma> + size \<tau> | Inr (_, \<sigma>, \<tau>) \<Rightarrow> size \<sigma> + size \<tau>,
     \<lambda>x. case x of Inl _ \<Rightarrow> 1 | Inr _ \<Rightarrow> 0]")
   (auto dest: size_list_zip_elem[where f = size and g = size])

fun elem_type :: "class_table \<Rightarrow> ty \<Rightarrow> ty option"
where
"elem_type \<Sigma> (TyList \<tau>) = Some \<tau>" |
"elem_type \<Sigma> (TyPrim str) = Some (TyPrim str)" |
"elem_type \<Sigma> (TyLiteral (LitString _)) = Some (TyPrim str)" |
"elem_type \<Sigma> (TyDict _) = Some (TyPrim str)" |
"elem_type \<Sigma> (TyClass C []) = (if C = range_class then Some (TyPrim int) else None)" |
"elem_type \<Sigma> (TyTuple \<tau>s) = Some (joins \<Sigma> (map base_type \<tau>s))" |
"elem_type \<Sigma> (TyUnion \<sigma> \<tau>) =
  (case (elem_type \<Sigma> \<sigma>, elem_type \<Sigma> \<tau>) of (Some \<sigma>', Some \<tau>') \<Rightarrow> Some (\<sigma>' \<squnion>\<^bsub>\<Sigma>\<^esub> \<tau>') | _ \<Rightarrow> None)" |
"elem_type \<Sigma> _ = None"

(* Type of a subscript, by the type of the subscripted value, the checks of the index against int and str,
   and the position and type synthesised by the index *)
fun subscript_type ::
  "class_table \<Rightarrow> ty \<Rightarrow> unit may_fail \<Rightarrow> unit may_fail \<Rightarrow> pos \<Rightarrow> ty may_fail \<Rightarrow> ty may_fail"
where
"subscript_type \<Sigma> (TyUnion \<sigma> \<sigma>') int_ok str_ok p idx = do {
   \<tau> \<leftarrow> subscript_type \<Sigma> \<sigma> int_ok str_ok p idx; \<tau>' \<leftarrow> subscript_type \<Sigma> \<sigma>' int_ok str_ok p idx;
   Ok (\<tau> \<squnion>\<^bsub>\<Sigma>\<^esub> \<tau>')
 }" |
"subscript_type \<Sigma> (TyList \<tau>) int_ok _ _ _ = do { int_ok; Ok \<tau> }" |
"subscript_type \<Sigma> (TyDict \<tau>) _ str_ok _ _ = do { str_ok; Ok \<tau> }" |
"subscript_type \<Sigma> (TyTuple \<tau>s) _ _ p idx = do {
   \<iota> \<leftarrow> idx;
   case \<iota> of
     TyLiteral (LitInt n) \<Rightarrow>
       let i = (if n < 0 then of_nat (length \<tau>s) + n else n)
       in if 0 \<le> i \<and> i < of_nat (length \<tau>s) then Ok (\<tau>s ! nat i)
          else Fail (Located p (TupleIndexOutOfRange n (length \<tau>s)))
   | TyPrim int \<Rightarrow> Ok (joins \<Sigma> \<tau>s)
   | _ \<Rightarrow> Fail (Located p (TypeMismatch (TyPrim int) \<iota>))
 }" |
"subscript_type \<Sigma> \<sigma> int_ok _ _ _ =
  (if base_type \<sigma> = TyPrim str then do { int_ok; Ok (TyPrim str) } else Fail (NotSubscriptable \<sigma>))"

datatype instances = Instance "ty list" | Undetermined | NoInstance

fun instance_above :: "class_table \<Rightarrow> name \<Rightarrow> ty \<Rightarrow> instances"
where
"instance_above \<Sigma> C (TyClass D \<sigma>s) =
  (if C \<in> set (ancestors \<Sigma> D) then Instance (instantiated_ancestor \<Sigma> D \<sigma>s C) else NoInstance)" |
"instance_above \<Sigma> C (TyPrim Never) = (if type_params \<Sigma> C = [] then Instance [] else Undetermined)" |
"instance_above \<Sigma> C _ = NoInstance"

definition instantiation_candidates :: "class_table \<Rightarrow> name \<Rightarrow> ty list \<Rightarrow> ty list list"
where
"instantiation_candidates \<Sigma> C \<sigma>s =
  product_lists
    (replicate (length (type_params \<Sigma> C))
      (map (joins \<Sigma>) (subseqs (remdups (concat (map subterms \<sigma>s) @ [TyPrim object])))))"

fun instance_below :: "class_table \<Rightarrow> name \<Rightarrow> ty \<Rightarrow> instances"
where
"instance_below \<Sigma> C (TyClass D \<sigma>s) =
  (if D \<in> set (ancestors \<Sigma> C) then
     (case
        filter (\<lambda>\<tau>s. list_all2 (\<lambda>\<rho> \<sigma>. \<Sigma> \<turnstile> \<rho> \<approx> \<sigma>) (instantiated_ancestor \<Sigma> C \<tau>s D) \<sigma>s)
          (instantiation_candidates \<Sigma> C \<sigma>s) of
        [] \<Rightarrow> NoInstance
      | \<tau>s # \<tau>ss \<Rightarrow>
          if list_all (list_all2 (\<lambda>\<tau> \<tau>'. \<Sigma> \<turnstile> \<tau> \<approx> \<tau>') \<tau>s) \<tau>ss then Instance \<tau>s else Undetermined)
   else NoInstance)" |
"instance_below \<Sigma> C (TyPrim object) = (if type_params \<Sigma> C = [] then Instance [] else Undetermined)" |
"instance_below \<Sigma> C _ = NoInstance"

definition instance_at :: "class_table \<Rightarrow> name \<Rightarrow> ty \<Rightarrow> instances"
where
"instance_at \<Sigma> C \<tau> = (case instance_above \<Sigma> C \<tau> of NoInstance \<Rightarrow> instance_below \<Sigma> C \<tau> | \<iota> \<Rightarrow> \<iota>)"

(* Pointwise join of contexts binding type variables at types *)
definition join_cxt :: "class_table \<Rightarrow> (var, ty) fmap \<Rightarrow> (var, ty) fmap \<Rightarrow> (var, ty) fmap"
where
"join_cxt \<Sigma> \<gamma> \<gamma>' =
  fmmap_keys (\<lambda>\<alpha> \<tau>. case (fmlookup \<gamma> \<alpha>, fmlookup \<gamma>' \<alpha>) of (Some \<sigma>, Some \<tau>') \<Rightarrow> \<sigma> \<squnion>\<^bsub>\<Sigma>\<^esub> \<tau>' | _ \<Rightarrow> \<tau>) (\<gamma> \<otimes> \<gamma>')"

function (sequential)
  type_args :: "class_table \<Rightarrow> var list \<Rightarrow> ty \<Rightarrow> ty \<Rightarrow> (var, ty) fmap" and
  type_args_seq :: "class_table \<Rightarrow> var list \<Rightarrow> ty list \<Rightarrow> ty list \<Rightarrow> (var, ty) fmap"
where
"type_args \<Sigma> \<alpha>s (TyVar \<alpha>) \<tau> =
  (if \<alpha> \<in> set \<alpha>s then fmupd \<alpha> (base_type \<tau>) fmempty else fmempty)" |
"type_args \<Sigma> \<alpha>s \<sigma> (TyUnion \<tau> \<tau>') = join_cxt \<Sigma> (type_args \<Sigma> \<alpha>s \<sigma> \<tau>) (type_args \<Sigma> \<alpha>s \<sigma> \<tau>')" |
"type_args \<Sigma> \<alpha>s (TyList \<sigma>) (TyList \<tau>) = type_args \<Sigma> \<alpha>s \<sigma> \<tau>" |
"type_args \<Sigma> \<alpha>s (TyDict \<sigma>) (TyDict \<tau>) = type_args \<Sigma> \<alpha>s \<sigma> \<tau>" |
"type_args \<Sigma> \<alpha>s (TyTuple \<sigma>s) (TyTuple \<tau>s) = type_args_seq \<Sigma> \<alpha>s \<sigma>s \<tau>s" |
"type_args \<Sigma> \<alpha>s (TyCallable \<sigma>s \<sigma>) (TyCallable \<tau>s \<tau>) = type_args_seq \<Sigma> \<alpha>s (\<sigma> # \<sigma>s) (\<tau> # \<tau>s)" |
"type_args \<Sigma> \<alpha>s (TyClass C \<sigma>s) \<tau> =
  (case instance_at \<Sigma> C \<tau> of Instance \<tau>s \<Rightarrow> type_args_seq \<Sigma> \<alpha>s \<sigma>s \<tau>s | _ \<Rightarrow> fmempty)" |
"type_args \<Sigma> \<alpha>s (TyUnion \<sigma> \<sigma>') \<tau> =
  (if (\<Sigma> \<turnstile> \<tau> <: \<sigma> \<and> fv \<sigma> \<inter> set \<alpha>s = {}) \<or> (\<Sigma> \<turnstile> \<tau> <: \<sigma>' \<and> fv \<sigma>' \<inter> set \<alpha>s = {}) then fmempty
   else join_cxt \<Sigma> (type_args \<Sigma> \<alpha>s \<sigma> \<tau>) (type_args \<Sigma> \<alpha>s \<sigma>' \<tau>))" |
"type_args \<Sigma> \<alpha>s _ _ = fmempty" |

"type_args_seq \<Sigma> \<alpha>s \<sigma>s \<tau>s = foldr (join_cxt \<Sigma>) (map2 (type_args \<Sigma> \<alpha>s) \<sigma>s \<tau>s) fmempty"
by pat_completeness auto

termination
by (relation "measures [
     \<lambda>x. case x of Inl (_, _, \<sigma>, _) \<Rightarrow> size \<sigma> | Inr (_, _, \<sigma>s, _) \<Rightarrow> size_list size \<sigma>s,
     \<lambda>x. case x of Inl _ \<Rightarrow> 1 | Inr _ \<Rightarrow> 0,
     \<lambda>x. case x of Inl (_, _, _, \<tau>) \<Rightarrow> size \<tau> | Inr _ \<Rightarrow> 0]")
   (auto dest: set_zip_leftD size_list_elem[where f = size])

(* Types bound to \<alpha>s by \<gamma>; failure if \<gamma> doesn't bind one of them *)
definition type_args_of :: "(var, ty) fmap \<Rightarrow> var list \<Rightarrow> ty list may_fail"
where
"type_args_of \<gamma> \<alpha>s =
  those_sum (map (\<lambda>\<alpha>. or_else (NoTypeArgument \<alpha>) (fmlookup \<gamma> \<alpha>)) \<alpha>s)"

(* Type of attribute x of a value of type \<sigma>, which isn't a module *)
fun attribute_type :: "class_table \<Rightarrow> ty \<Rightarrow> var \<Rightarrow> ty may_fail"
where
"attribute_type \<Sigma> (TyUnion \<sigma> \<sigma>') x =
  do { \<tau> \<leftarrow> attribute_type \<Sigma> \<sigma> x; \<tau>' \<leftarrow> attribute_type \<Sigma> \<sigma>' x; Ok (\<tau> \<squnion>\<^bsub>\<Sigma>\<^esub> \<tau>') }" |
"attribute_type \<Sigma> (TyClass C \<sigma>s) x =
  or_else (UnknownField (short_name C) x) (map_of (instantiate (fields \<Sigma> C) \<sigma>s) x)" |
"attribute_type \<Sigma> \<sigma> _ = Fail (NoAttributes \<sigma>)"

end
