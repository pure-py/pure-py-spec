(* Operator resolution and subtyping in executable form; Python generation *)
theory Codegen
  imports "mechanisation.Programs" "Python.Python_Setup"
begin

(* Floats as Python's float. Equality of representations, since HOL equality is reflexive; Python's == is given
   by the semantics *)
code_printing
    type_constructor float \<rightharpoonup> (Python) "float"
  | constant "HOL.equal :: float \<Rightarrow> float \<Rightarrow> bool" \<rightharpoonup> (Python) "(repr'(_') == repr'(_'))"

(* Strings as Python's str *)
code_printing
    type_constructor str \<rightharpoonup> (Python) "str"
  | constant "HOL.equal :: str \<Rightarrow> str \<Rightarrow> bool" \<rightharpoonup> (Python) "(_ == _)"
  | constant "(\<le>) :: str \<Rightarrow> str \<Rightarrow> bool" \<rightharpoonup> (Python) "(_ <= _)"
  | constant "(<) :: str \<Rightarrow> str \<Rightarrow> bool" \<rightharpoonup> (Python) "(_ < _)"
  | constant substring \<rightharpoonup> (Python) "(_ in _)"

(* Identifiers as Python's str *)
code_printing
    type_constructor var \<rightharpoonup> (Python) "str"
  | constant "HOL.equal :: var \<Rightarrow> var \<Rightarrow> bool" \<rightharpoonup> (Python) "(_ == _)"
  | constant "(\<le>) :: var \<Rightarrow> var \<Rightarrow> bool" \<rightharpoonup> (Python) "(_ <= _)"
  | constant "(<) :: var \<Rightarrow> var \<Rightarrow> bool" \<rightharpoonup> (Python) "(_ < _)"
  | constant var \<rightharpoonup> (Python) "\"\".join'(_')"

code_pred subty .
code_pred binop_overload .
code_pred unop_overload .

(* Compute sets of overloads by the predicates compiled above, since their defining comprehensions can't be
   executed *)
lemma binop_overloads_code [code]:
  "binop_overloads \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2 = set_of_pred (binop_overload_i_i_i_i_PPooo \<Sigma> op \<sigma>\<^sub>1 \<sigma>\<^sub>2)"
  by (auto simp: binop_overloads_def binop_overload_i_i_i_i_PPooo_def)

lemma unop_overloads_code [code]:
  "unop_overloads \<Sigma> op \<sigma> = set_of_pred (unop_overload_i_i_i_Poo \<Sigma> op \<sigma>)"
  by (auto simp: unop_overloads_def unop_overload_i_i_i_Poo_def)

export_code check_program
  in Python file_prefix "."

end
