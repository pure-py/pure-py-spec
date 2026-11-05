(* Floats as an abstract type with uninterpreted arithmetic *)
theory Floats
  imports "HOL-Library.Extended_Real"
begin

typedecl float

(* Value as an extended real; None for nan *)
consts float_value :: "float \<Rightarrow> ereal option"

(* Arithmetic of Python's float, left uninterpreted since type soundness doesn't depend on the results *)
consts
  float_of_int :: "int \<Rightarrow> float"
  float_neg :: "float \<Rightarrow> float"
  float_add :: "float \<Rightarrow> float \<Rightarrow> float"
  float_sub :: "float \<Rightarrow> float \<Rightarrow> float"
  float_mul :: "float \<Rightarrow> float \<Rightarrow> float"
  float_div :: "float \<Rightarrow> float \<Rightarrow> float"
  float_floordiv :: "float \<Rightarrow> float \<Rightarrow> float"
  float_mod :: "float \<Rightarrow> float \<Rightarrow> float"
  float_pow :: "float \<Rightarrow> float \<Rightarrow> float"

definition is_nan :: "float \<Rightarrow> bool"
where
"is_nan x = (float_value x = None)"

instantiation float :: equal
begin

definition equal_float :: "float \<Rightarrow> float \<Rightarrow> bool"
where
"equal_float x x' = (x = x')"

instance
  by standard (simp add: equal_float_def)

end

end
