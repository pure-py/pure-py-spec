(* Example evaluations *)
theory Examples
    imports Semantics
begin

definition ex_add :: expr
where "ex_add =
  ExprBinOp BOpAdd (At no_pos (ExprLiteral (LitInt 10))) (At no_pos (ExprLiteral (LitInt 20)))"

lemma ex_add_eval: "\<epsilon>, ex_add \<Rightarrow>\<^sub>e Val (VLit (LitInt 30))"
proof -
  have "\<epsilon>, ex_add \<Rightarrow>\<^sub>e mlet (Val (VLit (LitInt 20))) (binop_meaning BOpAdd (VLit (LitInt 10)))"
    unfolding ex_add_def by (rule EvalBinOp) (simp_all add: EvalLiteral)
  then show ?thesis by simp
qed

definition ex_lambda :: expr
where "ex_lambda =
    ExprCall
        (At no_pos (ExprLambda [var ''x'']
          (At no_pos
            (ExprBinOp BOpAdd (At no_pos (ExprVar (var ''x''))) (At no_pos (ExprLiteral (LitInt 1)))))))
        ([At no_pos (ExprLiteral (LitInt 2))], [])"

lemma ex_lambda_eval: "\<epsilon>, ex_lambda \<Rightarrow>\<^sub>e Val (VLit (LitInt 3))"
proof -
  have two: "\<epsilon>, node (At no_pos (ExprLiteral (LitInt 2))) \<Rightarrow>\<^sub>e Val (VLit (LitInt 2))"
    by (simp add: EvalLiteral)
  have args: "\<epsilon>, [At no_pos (ExprLiteral (LitInt 2))] \<Rightarrow>\<^sub>e\<^sub>s Val [VLit (LitInt 2)]"
    using EvalExprsCons[OF two EvalExprsNil] by simp
  let ?\<rho> = "\<epsilon> \<otimes> fmap_of_list (zip [var ''x''] [VLit (LitInt 2)])"
  have "?\<rho>, ExprVar (var ''x'') \<Rightarrow>\<^sub>e Val (VLit (LitInt 2))" by (rule EvalVar) simp_all
  then have x: "?\<rho>, node (At no_pos (ExprVar (var ''x''))) \<Rightarrow>\<^sub>e Val (VLit (LitInt 2))" by simp
  have one: "?\<rho>, node (At no_pos (ExprLiteral (LitInt 1))) \<Rightarrow>\<^sub>e Val (VLit (LitInt 1))"
    by (simp add: EvalLiteral)
  have "?\<rho>, ExprBinOp BOpAdd (At no_pos (ExprVar (var ''x''))) (At no_pos (ExprLiteral (LitInt 1)))
    \<Rightarrow>\<^sub>e mlet (Val (VLit (LitInt 1))) (binop_meaning BOpAdd (VLit (LitInt 2)))"
    by (rule EvalBinOp[OF x one])
  then have body:
    "?\<rho>, node (At no_pos
              (ExprBinOp BOpAdd (At no_pos (ExprVar (var ''x''))) (At no_pos (ExprLiteral (LitInt 1)))))
     \<Rightarrow>\<^sub>e Val (VLit (LitInt 3))"
    by simp
  show ?thesis
    unfolding ex_lambda_def by (rule EvalCallLambda[OF _ args _ body]) (simp_all add: EvalLambda)
qed

end
