(* Equality types and operator overloads *)
theory Operators
  imports Subtyping
begin

(* Pairs (C, \<xi>) at which the needs-eq judgement on classes is defined, with None for a callable type *)
definition needs_eq_dom :: "class_table \<Rightarrow> (name \<times> var option) set"
where
"needs_eq_dom \<Sigma> =
  {(C, \<xi>). fmlookup \<Sigma> C \<noteq> None \<and> (case \<xi> of None \<Rightarrow> True | Some \<alpha> \<Rightarrow> \<alpha> \<in> set (type_params \<Sigma> C))}"

lemma needs_eq_dom_mem [code_unfold]:
  "(C, \<xi>) \<in> needs_eq_dom \<Sigma> \<longleftrightarrow>
   fmlookup \<Sigma> C \<noteq> None \<and> (case \<xi> of None \<Rightarrow> True | Some \<alpha> \<Rightarrow> \<alpha> \<in> set (type_params \<Sigma> C))"
  by (simp add: needs_eq_dom_def)

lemma finite_needs_eq_dom: "finite (needs_eq_dom \<Sigma>)"
proof -
  have "needs_eq_dom \<Sigma> \<subseteq> fmdom' \<Sigma> \<times> insert None (Some ` (\<Union>C \<in> fmdom' \<Sigma>. set (type_params \<Sigma> C)))"
  proof
    fix p assume "p \<in> needs_eq_dom \<Sigma>"
    then obtain C \<xi> where p: "p = (C, \<xi>)" and "(C, \<xi>) \<in> needs_eq_dom \<Sigma>" by (cases p) auto
    then have C: "C \<in> fmdom' \<Sigma>" by (auto simp: needs_eq_dom_def fmlookup_dom'_iff[symmetric])
    show "p \<in> fmdom' \<Sigma> \<times> insert None (Some ` (\<Union>C \<in> fmdom' \<Sigma>. set (type_params \<Sigma> C)))"
      using \<open>(C, \<xi>) \<in> needs_eq_dom \<Sigma>\<close> C by (cases \<xi>) (auto simp: p needs_eq_dom_def image_iff)
  qed
  then show ?thesis by (rule finite_subset) simp
qed

lemma card_needs_eq_dom_pos:
  assumes "(C, \<xi>) \<in> needs_eq_dom \<Sigma>" and "(C, \<xi>) \<notin> D"
  shows "0 < card (needs_eq_dom \<Sigma> - D)"
  using assms by (simp add: card_gt_0_iff finite_needs_eq_dom) blast

(* D holds the pairs whose derivation is in progress; the result for a pair in D is False *)
function (sequential)
  needs_eq :: "class_table \<Rightarrow> (name \<times> var option) set \<Rightarrow> ty \<Rightarrow> var option \<Rightarrow> bool" and
  needs_eq_class :: "class_table \<Rightarrow> (name \<times> var option) set \<Rightarrow> name \<Rightarrow> var option \<Rightarrow> bool"
where
"needs_eq \<Sigma> D (TyVar \<alpha>) \<xi> = (\<xi> = Some \<alpha>)" |
"needs_eq \<Sigma> D (TyCallable _ _) \<xi> = (\<xi> = None)" |
"needs_eq \<Sigma> D (TyList \<tau>) \<xi> = needs_eq \<Sigma> D \<tau> \<xi>" |
"needs_eq \<Sigma> D (TyDict \<tau>) \<xi> = needs_eq \<Sigma> D \<tau> \<xi>" |
"needs_eq \<Sigma> D (TyTuple \<tau>s) \<xi> = list_ex (\<lambda>\<tau>. needs_eq \<Sigma> D \<tau> \<xi>) \<tau>s" |
"needs_eq \<Sigma> D (TyUnion \<sigma> \<tau>) \<xi> = (needs_eq \<Sigma> D \<sigma> \<xi> \<or> needs_eq \<Sigma> D \<tau> \<xi>)" |
"needs_eq \<Sigma> D (TyClass C \<sigma>s) \<xi> =
  ((\<xi> = None \<and> needs_eq_class \<Sigma> D C None) \<or>
   list_ex (\<lambda>(\<alpha>, \<sigma>). needs_eq_class \<Sigma> D C (Some \<alpha>) \<and> needs_eq \<Sigma> D \<sigma> \<xi>) (zip (type_params \<Sigma> C) \<sigma>s))" |
"needs_eq \<Sigma> D _ \<xi> = False" |

"needs_eq_class \<Sigma> D C \<xi> =
  (if (C, \<xi>) \<in> needs_eq_dom \<Sigma> \<and> (C, \<xi>) \<notin> D then
     (case fields \<Sigma> C of
        FieldScheme _ x\<tau>s \<Rightarrow> list_ex (\<lambda>(_, \<tau>). needs_eq \<Sigma> (insert (C, \<xi>) D) \<tau> \<xi>) x\<tau>s)
   else False)"
by pat_completeness auto

termination
by (relation "measures [
     \<lambda>x. case x of
       Inl (\<Sigma>, D, _, _) \<Rightarrow> card (needs_eq_dom \<Sigma> - D) | Inr (\<Sigma>, D, _, _) \<Rightarrow> card (needs_eq_dom \<Sigma> - D),
     \<lambda>x. case x of Inl (_, _, \<tau>, _) \<Rightarrow> size \<tau> | Inr _ \<Rightarrow> 0]")
   (auto simp: less_Suc_eq dest: set_zip_rightD card_needs_eq_dom_pos intro: size_list_elem)

(* \<tau> is an equality type: comparing its values never involves a type variable or a callable type *)
definition equality_type :: "class_table \<Rightarrow> ty \<Rightarrow> bool"
where
"equality_type \<Sigma> \<tau> = (\<not> needs_eq \<Sigma> {} \<tau> None \<and> (\<forall>\<alpha> \<in> fv \<tau>. \<not> needs_eq \<Sigma> {} \<tau> (Some \<alpha>)))"

abbreviation comparable :: "class_table \<Rightarrow> ty \<Rightarrow> ty \<Rightarrow> bool" where "comparable \<Sigma> \<sigma> \<tau> \<equiv> \<Sigma> \<turnstile> \<sigma> <: \<tau> \<or> \<Sigma> \<turnstile> \<tau> <: \<sigma>"

inductive binop_overload :: "class_table \<Rightarrow> bop \<Rightarrow> ty \<Rightarrow> ty \<Rightarrow> (ty \<times> ty) \<times> ty \<Rightarrow> bool"
for \<Sigma> :: class_table
where
OverloadEq:
  "\<lbrakk> op \<in> {BOpEq, BOpNeq} ; equality_type \<Sigma> \<sigma>\<^sub>1 ; equality_type \<Sigma> \<sigma>\<^sub>2 ; comparable \<Sigma> \<sigma>\<^sub>1 \<sigma>\<^sub>2 \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2 ((\<sigma>\<^sub>1, \<sigma>\<^sub>2), TyPrim bool)" |
OverloadInList:
  "\<lbrakk> op \<in> {BOpIn, BOpNotIn} ; comparable \<Sigma> \<sigma>\<^sub>1 \<tau> \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> op \<sigma>\<^sub>1 (TyList \<tau>) ((\<sigma>\<^sub>1, TyList \<tau>), TyPrim bool)" |
OverloadInTuple:
  "\<lbrakk> op \<in> {BOpIn, BOpNotIn} ; comparable \<Sigma> \<sigma>\<^sub>1 (joins \<Sigma> \<tau>s) \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> op \<sigma>\<^sub>1 (TyTuple \<tau>s) ((\<sigma>\<^sub>1, TyTuple \<tau>s), TyPrim bool)" |
OverloadInStr:
  "\<lbrakk> op \<in> {BOpIn, BOpNotIn} ; \<Sigma> \<turnstile> \<sigma>\<^sub>1 <: TyPrim str ; \<Sigma> \<turnstile> \<sigma>\<^sub>2 <: TyPrim str \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2 ((TyPrim str, TyPrim str), TyPrim bool)" |
OverloadInDict:
  "\<lbrakk> op \<in> {BOpIn, BOpNotIn} ; \<Sigma> \<turnstile> \<sigma>\<^sub>1 <: TyPrim str \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> op \<sigma>\<^sub>1 (TyDict \<tau>) ((TyPrim str, TyDict \<tau>), TyPrim bool)" |
OverloadOrderFloat:
  "\<lbrakk> op \<in> {BOpLt, BOpLeq, BOpGt, BOpGeq} ; \<Sigma> \<turnstile> \<sigma>\<^sub>1 <: TyPrim float ; \<Sigma> \<turnstile> \<sigma>\<^sub>2 <: TyPrim float \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2 ((TyPrim float, TyPrim float), TyPrim bool)" |
OverloadOrderStr:
  "\<lbrakk> op \<in> {BOpLt, BOpLeq, BOpGt, BOpGeq} ; \<Sigma> \<turnstile> \<sigma>\<^sub>1 <: TyPrim str ; \<Sigma> \<turnstile> \<sigma>\<^sub>2 <: TyPrim str \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2 ((TyPrim str, TyPrim str), TyPrim bool)" |
OverloadArithInt:
  "\<lbrakk> op \<in> {BOpAdd, BOpSub, BOpMul, BOpFloorDiv, BOpMod} ; \<Sigma> \<turnstile> \<sigma>\<^sub>1 <: TyPrim int ; \<Sigma> \<turnstile> \<sigma>\<^sub>2 <: TyPrim int \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2 ((TyPrim int, TyPrim int), TyPrim int)" |
OverloadArithFloat:
  "\<lbrakk> op \<in> {BOpAdd, BOpSub, BOpMul, BOpFloorDiv, BOpMod, BOpDiv, BOpPow} ; \<Sigma> \<turnstile> \<sigma>\<^sub>1 <: TyPrim float
   ; \<Sigma> \<turnstile> \<sigma>\<^sub>2 <: TyPrim float \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2 ((TyPrim float, TyPrim float), TyPrim float)" |
OverloadAddStr:
  "\<lbrakk> \<Sigma> \<turnstile> \<sigma>\<^sub>1 <: TyPrim str ; \<Sigma> \<turnstile> \<sigma>\<^sub>2 <: TyPrim str \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> BOpAdd \<sigma>\<^sub>1 \<sigma>\<^sub>2 ((TyPrim str, TyPrim str), TyPrim str)" |
OverloadAddList: "binop_overload \<Sigma> BOpAdd (TyList \<sigma>) (TyList \<tau>) ((TyList \<sigma>, TyList \<tau>), TyList (\<sigma> \<squnion>\<^bsub>\<Sigma>\<^esub> \<tau>))" |
OverloadAddTuple:
  "binop_overload \<Sigma> BOpAdd (TyTuple \<sigma>s) (TyTuple \<tau>s) ((TyTuple \<sigma>s, TyTuple \<tau>s), TyTuple (\<sigma>s @ \<tau>s))" |
OverloadMulStrInt:
  "\<lbrakk> \<Sigma> \<turnstile> \<sigma>\<^sub>1 <: TyPrim str ; \<Sigma> \<turnstile> \<sigma>\<^sub>2 <: TyPrim int \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> BOpMul \<sigma>\<^sub>1 \<sigma>\<^sub>2 ((TyPrim str, TyPrim int), TyPrim str)" |
OverloadMulIntStr:
  "\<lbrakk> \<Sigma> \<turnstile> \<sigma>\<^sub>1 <: TyPrim int ; \<Sigma> \<turnstile> \<sigma>\<^sub>2 <: TyPrim str \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> BOpMul \<sigma>\<^sub>1 \<sigma>\<^sub>2 ((TyPrim int, TyPrim str), TyPrim str)" |
OverloadMulListInt:
  "\<Sigma> \<turnstile> \<sigma>\<^sub>2 <: TyPrim int \<Longrightarrow> binop_overload \<Sigma> BOpMul (TyList \<tau>) \<sigma>\<^sub>2 ((TyList \<tau>, TyPrim int), TyList \<tau>)" |
OverloadMulIntList:
  "\<Sigma> \<turnstile> \<sigma>\<^sub>1 <: TyPrim int \<Longrightarrow> binop_overload \<Sigma> BOpMul \<sigma>\<^sub>1 (TyList \<tau>) ((TyPrim int, TyList \<tau>), TyList \<tau>)" |
OverloadPowNat:
  "\<lbrakk> \<Sigma> \<turnstile> \<sigma>\<^sub>1 <: TyPrim int ; n \<ge> 0 \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> BOpPow \<sigma>\<^sub>1 (TyLiteral (LitInt n)) ((TyPrim int, TyLiteral (LitInt n)), TyPrim int)" |
OverloadPowNeg:
  "\<lbrakk> \<Sigma> \<turnstile> \<sigma>\<^sub>1 <: TyPrim int ; n < 0 \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> BOpPow \<sigma>\<^sub>1 (TyLiteral (LitInt n)) ((TyPrim int, TyLiteral (LitInt n)), TyPrim float)" |
OverloadBase:
  "\<lbrakk> literal_type \<sigma>\<^sub>1 \<or> literal_type \<sigma>\<^sub>2 ; binop_overload \<Sigma> op (base_type \<sigma>\<^sub>1) (base_type \<sigma>\<^sub>2) ((\<tau>\<^sub>1, \<tau>\<^sub>2), \<tau>) \<rbrakk>
  \<Longrightarrow> binop_overload \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2 ((\<tau>\<^sub>1, \<tau>\<^sub>2), \<tau>)"

inductive unop_overload :: "class_table \<Rightarrow> uop \<Rightarrow> ty \<Rightarrow> ty \<times> ty \<Rightarrow> bool"
for \<Sigma> :: class_table
where
UnopOverloadNot: "\<Sigma> \<turnstile> \<sigma> <: TyPrim bool \<Longrightarrow> unop_overload \<Sigma> UOpNot \<sigma> (TyPrim bool, TyPrim bool)" |
UnopOverloadInt:
  "\<lbrakk> op \<in> {UOpPos, UOpNeg} ; \<Sigma> \<turnstile> \<sigma> <: TyPrim int \<rbrakk> \<Longrightarrow> unop_overload \<Sigma> op \<sigma> (TyPrim int, TyPrim int)" |
UnopOverloadFloat:
  "\<lbrakk> op \<in> {UOpPos, UOpNeg} ; \<Sigma> \<turnstile> \<sigma> <: TyPrim float \<rbrakk> \<Longrightarrow> unop_overload \<Sigma> op \<sigma> (TyPrim float, TyPrim float)" |
UnopOverloadBase:
  "\<lbrakk> literal_type \<sigma> ; unop_overload \<Sigma> op (base_type \<sigma>) (\<tau>, \<tau>') \<rbrakk> \<Longrightarrow> unop_overload \<Sigma> op \<sigma> (\<tau>, \<tau>')"

definition binop_overloads :: "class_table \<Rightarrow> bop \<Rightarrow> ty \<Rightarrow> ty \<Rightarrow> ((ty \<times> ty) \<times> ty) set"
where
"binop_overloads \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2 = {\<omega>. binop_overload \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2 \<omega>}"

definition unop_overloads :: "class_table \<Rightarrow> uop \<Rightarrow> ty \<Rightarrow> (ty \<times> ty) set"
where
"unop_overloads \<Sigma> op \<sigma> = {\<omega>. unop_overload \<Sigma> op \<sigma> \<omega>}"

definition resolve_binop :: "class_table \<Rightarrow> bop \<Rightarrow> ty \<Rightarrow> ty \<Rightarrow> ty option"
where
"resolve_binop \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2 =
  (let overloads = binop_overloads \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2;
       most_specific =
         Set.filter (\<lambda>((\<tau>\<^sub>1, \<tau>\<^sub>2), _). \<forall>((\<tau>\<^sub>1', \<tau>\<^sub>2'), _) \<in> overloads. \<Sigma> \<turnstile> \<tau>\<^sub>1 <: \<tau>\<^sub>1' \<and> \<Sigma> \<turnstile> \<tau>\<^sub>2 <: \<tau>\<^sub>2') overloads in
   if is_singleton most_specific then Some (snd (the_elem most_specific)) else None)"

definition resolve_unop :: "class_table \<Rightarrow> uop \<Rightarrow> ty \<Rightarrow> ty option"
where
"resolve_unop \<Sigma> op \<sigma> =
  (let overloads = unop_overloads \<Sigma> op \<sigma>;
       most_specific = Set.filter (\<lambda>(\<tau>, _). \<forall>(\<tau>', _) \<in> overloads. \<Sigma> \<turnstile> \<tau> <: \<tau>') overloads in
   if is_singleton most_specific then Some (snd (the_elem most_specific)) else None)"

end
