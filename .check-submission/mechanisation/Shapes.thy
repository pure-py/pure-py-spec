(* Heads and shapes for pattern matching; head and shape typing; shapes of a type *)
theory Shapes
  imports Subtyping
begin

datatype head = HeadLiteral lit | HeadClass name | HeadList nat

datatype shape =
    ShapeRest ty "head set"
  | ShapeConstr name "ty list" "shape list" "head set"
  | ShapeTuple "shape list"
  | ShapeList ty "shape list"
  | ShapeDict ty "(str \<times> shape) list" "str set"

fun head_typed :: "class_table \<Rightarrow> head \<Rightarrow> ty \<Rightarrow> bool"
where
"head_typed \<Sigma> (HeadLiteral (LitFloat _)) \<tau> = (\<Sigma> \<turnstile> TyPrim float <: \<tau>)" |
"head_typed \<Sigma> (HeadLiteral l) \<tau> = (\<Sigma> \<turnstile> TyLiteral l <: \<tau>)" |
"head_typed \<Sigma> (HeadClass C) (TyUnion \<sigma> \<tau>) = (head_typed \<Sigma> (HeadClass C) \<sigma> \<or> head_typed \<Sigma> (HeadClass C) \<tau>)" |
"head_typed \<Sigma> (HeadClass C) (TyPrim Sized) = (C = range_class)" |
"head_typed \<Sigma> (HeadClass C) \<tau> = (instance_below \<Sigma> C \<tau> \<noteq> NoInstance)" |
"head_typed \<Sigma> (HeadList _) (TyList _) = True" |
"head_typed \<Sigma> (HeadList _) _ = False"

inductive shape_typed :: "class_table \<Rightarrow> shape \<Rightarrow> ty \<Rightarrow> bool"
for \<Sigma> :: class_table
where
ShapeRest:
  "\<lbrakk> \<forall>h \<in> H. head_typed \<Sigma> h \<tau> ; case \<tau> of TyUnion _ _ \<Rightarrow> False | TyDict _ \<Rightarrow> False | _ \<Rightarrow> True \<rbrakk>
  \<Longrightarrow> shape_typed \<Sigma> (ShapeRest \<tau> H) \<tau>" |
ShapeConstr:
  "\<lbrakk> \<forall>h \<in> H. head_typed \<Sigma> h (TyClass C \<tau>s) ;
     list_all2 (shape_typed \<Sigma>) ks (field_types \<Sigma> C \<tau>s) \<rbrakk>
  \<Longrightarrow> shape_typed \<Sigma> (ShapeConstr C \<tau>s ks H) (TyClass C \<tau>s)" |
ShapeTuple: "list_all2 (shape_typed \<Sigma>) ks \<tau>s \<Longrightarrow> shape_typed \<Sigma> (ShapeTuple ks) (TyTuple \<tau>s)" |
ShapeList: "\<forall>k \<in> set ks. shape_typed \<Sigma> k \<tau> \<Longrightarrow> shape_typed \<Sigma> (ShapeList \<tau> ks) (TyList \<tau>)" |
ShapeSub: "\<lbrakk> shape_typed \<Sigma> k \<sigma> ; \<Sigma> \<turnstile> \<sigma> <: \<tau> \<rbrakk> \<Longrightarrow> shape_typed \<Sigma> k \<tau>" |
ShapeDict:
  "\<lbrakk> \<forall>w \<in> W. head_typed \<Sigma> (HeadLiteral (LitString w)) (TyPrim str) ; \<forall>(w, k) \<in> set \<beta>. shape_typed \<Sigma> k \<tau> ;
     fst ` set \<beta> \<inter> W = {} \<rbrakk>
  \<Longrightarrow> shape_typed \<Sigma> (ShapeDict \<tau> \<beta> W) (TyDict \<tau>)"

fun shape_type :: "shape \<Rightarrow> ty"
where
"shape_type (ShapeRest \<tau> _) = \<tau>" |
"shape_type (ShapeConstr C \<tau>s _ _) = TyClass C \<tau>s" |
"shape_type (ShapeTuple ks) = TyTuple (map shape_type ks)" |
"shape_type (ShapeList \<tau> _) = TyList \<tau>" |
"shape_type (ShapeDict \<tau> _ _) = TyDict \<tau>"

(* \<beta> with keys ws bound to shapes ks *)
definition with_keys :: "(str \<times> shape) list \<Rightarrow> str list \<Rightarrow> shape list \<Rightarrow> (str \<times> shape) list"
where
"with_keys \<beta> ws ks = sort_key fst (zip ws ks @ filter (\<lambda>(w, _). w \<notin> set ws) \<beta>)"

definition below_excluded :: "class_table \<Rightarrow> name \<Rightarrow> head set \<Rightarrow> bool"
where
"below_excluded \<Sigma> C H = (\<exists>D \<in> set (ancestors \<Sigma> C). HeadClass D \<in> H)"

fun exhausts :: "class_table \<Rightarrow> head set \<Rightarrow> ty \<Rightarrow> bool"
where
"exhausts \<Sigma> H (TyLiteral l) = (HeadLiteral l \<in> H)" |
"exhausts \<Sigma> H (TyPrim bool) = (HeadLiteral (LitBool True) \<in> H \<and> HeadLiteral (LitBool False) \<in> H)" |
"exhausts \<Sigma> H (TyPrim NoneType) = (HeadLiteral LitNone \<in> H)" |
"exhausts \<Sigma> H (TyClass C _) = below_excluded \<Sigma> C H" |
"exhausts \<Sigma> H (TyPrim Never) = True" |
"exhausts \<Sigma> H _ = False"

definition typed_heads :: "class_table \<Rightarrow> head set \<Rightarrow> ty \<Rightarrow> head set"
where
"typed_heads \<Sigma> H \<tau> = Set.filter (\<lambda>h. head_typed \<Sigma> h \<tau>) H"

fun shapes :: "class_table \<Rightarrow> ty \<Rightarrow> head set \<Rightarrow> shape list"
where
"shapes \<Sigma> (TyUnion \<sigma> \<tau>) H =
  (let K = shapes \<Sigma> \<sigma> (typed_heads \<Sigma> H \<sigma>) in K @ filter (\<lambda>k. k \<notin> set K) (shapes \<Sigma> \<tau> (typed_heads \<Sigma> H \<tau>)))" |
"shapes \<Sigma> (TyDict \<tau>) H = [ShapeDict \<tau> [] {}]" |
"shapes \<Sigma> \<tau> H = (if exhausts \<Sigma> H \<tau> then [] else [ShapeRest \<tau> H])"

definition shapes_seq :: "class_table \<Rightarrow> ty list \<Rightarrow> shape list list"
where
"shapes_seq \<Sigma> \<tau>s = product_lists (map (\<lambda>\<tau>. shapes \<Sigma> \<tau> {}) \<tau>s)"

end
