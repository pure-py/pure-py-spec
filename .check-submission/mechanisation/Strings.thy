(* Strings and identifiers as lists of Unicode code points *)
theory Strings
  imports "HOL-Library.List_Lexorder"
begin

definition code_point_list :: "nat list set"
where
"code_point_list = {ns. \<forall>n \<in> set ns. n < 0x110000}"

lemma code_point_list_of_string: "map of_char s \<in> code_point_list"
  by (auto simp: code_point_list_def of_char_def)

typedef str = code_point_list
  morphisms code_points Str
  by (rule exI[of _ "[]"]) (simp add: code_point_list_def)

setup_lifting type_definition_str

lift_definition substring :: "str \<Rightarrow> str \<Rightarrow> bool"
  is "\<lambda>ns ns'. \<exists>ms ms'. ns' = ms @ ns @ ms'" .

instantiation str :: equal
begin

definition equal_str :: "str \<Rightarrow> str \<Rightarrow> bool"
where
"equal_str w w' = (w = w')"

instance
  by standard (simp add: equal_str_def)

end

instantiation str :: linorder
begin

lift_definition less_eq_str :: "str \<Rightarrow> str \<Rightarrow> bool" is "(\<le>)" .

lift_definition less_str :: "str \<Rightarrow> str \<Rightarrow> bool" is "(<)" .

instance
  by (standard; transfer) (auto simp: less_le_not_le linear intro: order_trans antisym)

end

typedef var = code_point_list
  morphisms var_code_points Var
  by (rule exI[of _ "[]"]) (simp add: code_point_list_def)

setup_lifting type_definition_var

(* Identifier written in a theory *)
lift_definition var :: "string \<Rightarrow> var"
  is "map of_char"
  by (rule code_point_list_of_string)

lemma var_inject [simp]: "var s = var s' \<longleftrightarrow> s = s'"
  by transfer (simp add: inj_map_eq_map inj_def of_char_eq_iff)

instantiation var :: equal
begin

definition equal_var :: "var \<Rightarrow> var \<Rightarrow> bool"
where
"equal_var x x' = (x = x')"

instance
  by standard (simp add: equal_var_def)

end

instantiation var :: linorder
begin

lift_definition less_eq_var :: "var \<Rightarrow> var \<Rightarrow> bool" is "(\<le>)" .

lift_definition less_var :: "var \<Rightarrow> var \<Rightarrow> bool" is "(<)" .

instance
  by (standard; transfer) (auto simp: less_le_not_le linear intro: order_trans antisym)

end

end
