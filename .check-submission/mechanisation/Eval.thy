theory Eval
    imports Semantics
begin

(* fun 
    eval_expr :: "\<rho> \<Rightarrow> expr \<Rightarrow> val option" and
    eval_exprs :: "\<rho> \<Rightarrow> expr list \<Rightarrow> val list option"
where
"eval_expr \<rho> (Var x) = map_of \<rho> x" | 
"eval_expr \<rho> (Literal l) = Some (VLit l)" |
"eval_expr \<rho> (BinOp op e1 e2) = 
    (case eval_expr \<rho> e1 of
       None \<Rightarrow> None
     | Some v1 \<Rightarrow>
       (case eval_expr \<rho> e2 of
          None \<Rightarrow> None
        | Some v2 \<Rightarrow> binop_eval op v1 v2))" | 
"eval_expr \<rho> (UnOp op e) =
    (case eval_expr \<rho> e of
       None \<Rightarrow> None
     | Some v \<Rightarrow> unop_eval op v)" | 
"eval_expr \<rho> (CondExpr e1 c e2) =
    (case eval_expr \<rho> c of
       Some (VLit (Bool True))  \<Rightarrow> eval_expr \<rho> e1
     | Some (VLit (Bool False)) \<Rightarrow> eval_expr \<rho> e2
     | _ \<Rightarrow> None)" | 
"eval_expr \<rho> (List es) =
    (case eval_exprs \<rho> es of
       None \<Rightarrow> None
     | Some vs \<Rightarrow> Some (VList vs))" | 
"eval_expr \<rho> (Tuple es) =
    (case eval_exprs \<rho> es of
       None \<Rightarrow> None
     | Some vs \<Rightarrow> Some (VTuple vs))" | 
"eval_expr \<rho> (Lambda x e) = Some (VClosure \<rho> x e)" |

"eval_exprs \<rho> [] = Some []" | 
"eval_exprs \<rho> (e # es) = 
    (case eval_expr \<rho> e of
       None \<Rightarrow> None
     | Some v \<Rightarrow>
       (case eval_exprs \<rho> es of
          None \<Rightarrow> None
        | Some vs \<Rightarrow> Some (v # vs)))" *)

end