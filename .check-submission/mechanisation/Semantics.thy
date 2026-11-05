(* Values, results and evaluation judgements *)
theory Semantics
    imports Syntax "HOL-Library.Finite_Map"
begin

(* Free o for outcomes, as in the spec *)
no_notation (ASCII) comp (infixl \<open>o\<close> 55)

datatype val =
      VLit lit
    | VList "val list"
    | VTuple "val list"
    | VLamClosure "(var, val) fmap" "var list" "expr located"  ("Lam'(_, _, _')")
    | VDefClosure "(var, val) fmap" "func located list" nat  ("Def'(_, _, _')")
    | VUnbound

type_synonym env = "(var, val) fmap"
abbreviation \<epsilon> :: env where "\<epsilon> \<equiv> fmempty"

datatype termination_kind =
    TypeError
  | IndexError
  | KeyError
  | OverflowError
  | ValueError
  | ZeroDivisionError
  | AssertionError "str option"
  | AttributeError
  | NameError
  | SystemExit int
  | Undef
  | Excluded

datatype 'a result = Val 'a | Aborts termination_kind

datatype outcome = Assigns env | Returns val | Aborts\<^sub>o termination_kind

consts mlet :: "'a result \<Rightarrow> ('a \<Rightarrow> 'b) \<Rightarrow> 'b"

fun mlet_result :: "'a result \<Rightarrow> ('a \<Rightarrow> 'b result) \<Rightarrow> 'b result"
where
"mlet_result (Val v) f = f v" |
"mlet_result (Aborts \<kappa>) f = Aborts \<kappa>"

fun mlet_outcome :: "'a result \<Rightarrow> ('a \<Rightarrow> outcome) \<Rightarrow> outcome"
where
"mlet_outcome (Val v) f = f v" |
"mlet_outcome (Aborts \<kappa>) f = Aborts\<^sub>o \<kappa>"

adhoc_overloading mlet \<rightleftharpoons> mlet_result mlet_outcome

fun compose :: "outcome \<Rightarrow> outcome \<Rightarrow> outcome" (infixl "\<otimes>\<^sub>o" 100)
where
"Assigns \<rho> \<otimes>\<^sub>o Assigns \<rho>' = Assigns (\<rho> \<otimes> \<rho>')" |
"Assigns \<rho> \<otimes>\<^sub>o o = o" |
"Returns v \<otimes>\<^sub>o o = Returns v" |
"Aborts\<^sub>o \<kappa> \<otimes>\<^sub>o o = Aborts\<^sub>o \<kappa>"

fun call_result :: "outcome \<Rightarrow> val result"
where
"call_result (Returns v) = Val v" |
"call_result (Assigns \<rho>) = Val (VLit LitNone)" |
"call_result (Aborts\<^sub>o \<kappa>) = Aborts \<kappa>"

fun is_closure :: "val \<Rightarrow> bool"
where
"is_closure Lam(_, _, _) = True" |
"is_closure Def(_, _, _) = True" |
"is_closure _ = False"

fun eq :: "val \<Rightarrow> val \<Rightarrow> bool result" and eq_elems :: "val list \<Rightarrow> val list \<Rightarrow> bool result"
where
"eq (VLit (LitInt n)) (VLit (LitInt n')) = Val (n = n')" |
"eq (VLit (LitInt n)) (VLit (LitFloat x')) = Val (float_value x' = Some (ereal (real_of_int n)))" |
"eq (VLit (LitFloat x)) (VLit (LitInt n')) = Val (float_value x = Some (ereal (real_of_int n')))" |
"eq (VLit (LitFloat x)) (VLit (LitFloat x')) =
  (if is_nan x \<and> is_nan x' then Aborts Undef else Val (float_value x = float_value x'))" |
"eq (VLit (LitString w)) (VLit (LitString w')) = Val (w = w')" |
"eq (VLit (LitBool b)) (VLit (LitBool b')) = Val (b = b')" |
"eq (VLit LitNone) (VLit LitNone) = Val True" |
"eq (VLit (LitBool _)) (VLit (LitInt _)) = Aborts Undef" |
"eq (VLit (LitBool _)) (VLit (LitFloat _)) = Aborts Undef" |
"eq (VLit (LitInt _)) (VLit (LitBool _)) = Aborts Undef" |
"eq (VLit (LitFloat _)) (VLit (LitBool _)) = Aborts Undef" |
"eq (VList vs) (VList vs') = eq_elems vs vs'" |
"eq (VTuple vs) (VTuple vs') = eq_elems vs vs'" |
"eq Lam(_, _, _) Lam(_, _, _) = Aborts Undef" |
"eq Lam(_, _, _) Def(_, _, _) = Aborts Undef" |
"eq Def(_, _, _) Lam(_, _, _) = Aborts Undef" |
"eq Def(_, _, _) Def(_, _, _) = Aborts Undef" |
"eq _ _ = Val False" |

"eq_elems [] [] = Val True" |
"eq_elems (v # vs) (v' # vs') =
  (if length vs \<noteq> length vs' then Val False
   else if eq v v' = Val True then eq_elems vs vs' else eq v v')" |
"eq_elems _ _ = Val False"

fun contains :: "val \<Rightarrow> val \<Rightarrow> bool result" and contains_elems :: "val list \<Rightarrow> val \<Rightarrow> bool result"
where
"contains (VList vs) v = contains_elems vs v" |
"contains (VTuple vs) v = contains_elems vs v" |
"contains (VLit (LitString w')) (VLit (LitString w)) = Val (substring w w')" |
"contains _ _ = Aborts TypeError" |

"contains_elems [] v = Val False" |
"contains_elems (v' # vs) v = (if eq v v' = Val False then contains_elems vs v else eq v v')"

fun is_bool :: "val \<Rightarrow> bool"
where
"is_bool (VLit (LitBool _)) = True" |
"is_bool _ = False"

fun is_nan_val :: "val \<Rightarrow> bool"
where
"is_nan_val (VLit (LitFloat x)) = is_nan x" |
"is_nan_val _ = False"

(* Float of an int or float value; None otherwise *)
fun as_float :: "val \<Rightarrow> float option"
where
"as_float (VLit (LitInt n)) = Some (float_of_int n)" |
"as_float (VLit (LitFloat x)) = Some x" |
"as_float _ = None"

(* Value of a number as an extended real; None for nan and for a non-number *)
fun number_value :: "val \<Rightarrow> ereal option"
where
"number_value (VLit (LitInt n)) = Some (ereal (real_of_int n))" |
"number_value (VLit (LitFloat x)) = float_value x" |
"number_value _ = None"

(* Apply g to two numbers as floats; Excluded for a Boolean operand *)
fun number_op :: "(float \<Rightarrow> float \<Rightarrow> val result) \<Rightarrow> val \<Rightarrow> val \<Rightarrow> val result"
where
"number_op g v v' =
  (if is_bool v \<or> is_bool v' then Aborts Excluded
   else case (as_float v, as_float v') of
     (Some x, Some x') \<Rightarrow> g x x'
   | _ \<Rightarrow> Aborts TypeError)"

(* Apply f to two integers, g to two numbers otherwise *)
fun arith :: "(int \<Rightarrow> int \<Rightarrow> int) \<Rightarrow> (float \<Rightarrow> float \<Rightarrow> float) \<Rightarrow> val \<Rightarrow> val \<Rightarrow> val result"
where
"arith f g (VLit (LitInt n)) (VLit (LitInt n')) = Val (VLit (LitInt (f n n')))" |
"arith f g v v' = number_op (\<lambda>x x'. Val (VLit (LitFloat (g x x')))) v v'"

(* Compare two numbers by value; false if either is nan *)
fun compare :: "(ereal \<Rightarrow> ereal \<Rightarrow> bool) \<Rightarrow> val \<Rightarrow> val \<Rightarrow> val result"
where
"compare f v v' =
  number_op (\<lambda>_ _. Val (VLit (LitBool (case (number_value v, number_value v') of
    (Some y, Some y') \<Rightarrow> f y y'
  | _ \<Rightarrow> False)))) v v'"

fun binop_meaning :: "bop \<Rightarrow> val \<Rightarrow> val \<Rightarrow> val result"
where
"binop_meaning BOpEq v v' =
  (if is_nan_val v \<and> is_nan_val v' then Val (VLit (LitBool False))
   else mlet (eq v v') (\<lambda>b. Val (VLit (LitBool b))))" |
"binop_meaning BOpNeq v v' =
  (if is_nan_val v \<and> is_nan_val v' then Val (VLit (LitBool True))
   else mlet (eq v v') (\<lambda>b. Val (VLit (LitBool (\<not> b)))))" |
"binop_meaning BOpIn v v' = mlet (contains v' v) (\<lambda>b. Val (VLit (LitBool b)))" |
"binop_meaning BOpNotIn v v' = mlet (contains v' v) (\<lambda>b. Val (VLit (LitBool (\<not> b))))" |
"binop_meaning BOpLt v v' = compare (<) v v'" |
"binop_meaning BOpLeq v v' = compare (\<le>) v v'" |
"binop_meaning BOpGt v v' = compare (>) v v'" |
"binop_meaning BOpGeq v v' = compare (\<ge>) v v'" |
"binop_meaning BOpAdd v v' = arith (+) float_add v v'" |
"binop_meaning BOpSub v v' = arith (-) float_sub v v'" |
"binop_meaning BOpMul v v' = arith (*) float_mul v v'" |
"binop_meaning BOpDiv v v' =
  (if number_value v' = Some 0 then Aborts ZeroDivisionError
   else number_op (\<lambda>x x'. Val (VLit (LitFloat (float_div x x')))) v v')" |
"binop_meaning BOpFloorDiv v v' =
  (if number_value v' = Some 0 then Aborts ZeroDivisionError else arith (div) float_floordiv v v')" |
"binop_meaning BOpMod v v' =
  (if number_value v' = Some 0 then Aborts ZeroDivisionError else arith (mod) float_mod v v')" |
"binop_meaning BOpPow (VLit (LitInt n)) (VLit (LitInt n')) =
  (if n' \<ge> 0 then Val (VLit (LitInt (n ^ nat n')))
   else if n = 0 then Aborts ZeroDivisionError
   else Val (VLit (LitFloat (float_pow (float_of_int n) (float_of_int n')))))" |
"binop_meaning BOpPow v v' =
  (if number_value v = Some 0 \<and> (\<exists>y. number_value v' = Some y \<and> y < 0) then Aborts ZeroDivisionError
   else number_op (\<lambda>x x'. Val (VLit (LitFloat (float_pow x x')))) v v')" |
"binop_meaning _ _ _ = Aborts TypeError"

fun unop_meaning :: "uop \<Rightarrow> val \<Rightarrow> val result"
where
"unop_meaning UOpNot (VLit (LitBool b)) = Val (VLit (LitBool (\<not> b)))" |
"unop_meaning UOpPos (VLit (LitInt n)) = Val (VLit (LitInt n))" |
"unop_meaning UOpPos (VLit (LitFloat x)) = Val (VLit (LitFloat x))" |
"unop_meaning UOpNeg (VLit (LitInt n)) = Val (VLit (LitInt (- n)))" |
"unop_meaning UOpNeg (VLit (LitFloat x)) = Val (VLit (LitFloat (float_neg x)))" |
"unop_meaning UOpNot _ = Aborts Excluded" |
"unop_meaning _ (VLit (LitBool _)) = Aborts Excluded" |
"unop_meaning _ _ = Aborts TypeError"

abbreviation true :: val where "true \<equiv> VLit (LitBool True)"
abbreviation false :: val where "false \<equiv> VLit (LitBool False)"

type_synonym elif_block = "(expr located \<times> stmt located) list \<times> stmt located option"

inductive
  eval_expr  :: "env \<Rightarrow> expr \<Rightarrow> val result \<Rightarrow> bool"            ("_, _ \<Rightarrow>\<^sub>e _" [60,0,60] 60) and
  eval_exprs :: "env \<Rightarrow> expr located list \<Rightarrow> val list result \<Rightarrow> bool"  ("_, _ \<Rightarrow>\<^sub>e\<^sub>s _" [60,0,60] 60) and
  eval_stmt  :: "env \<Rightarrow> stmt \<Rightarrow> outcome \<Rightarrow> bool"               ("_, _ \<Rightarrow>\<^sub>s _" [60,0,60] 60) and
  eval_elif  :: "env \<Rightarrow> elif_block \<Rightarrow> outcome \<Rightarrow> bool"         ("_, _ \<Rightarrow>\<^sub>e\<^sub>l\<^sub>i\<^sub>f _" [60,0,60] 60)
where
EvalVar: "\<lbrakk> fmlookup \<rho> x = Some v ; v \<noteq> VUnbound \<rbrakk> \<Longrightarrow> \<rho>, ExprVar x \<Rightarrow>\<^sub>e Val v" |
EvalVarUnknown: "fmlookup \<rho> x = None \<Longrightarrow> \<rho>, ExprVar x \<Rightarrow>\<^sub>e Aborts NameError" |
EvalVarUnbound: "fmlookup \<rho> x = Some VUnbound \<Longrightarrow> \<rho>, ExprVar x \<Rightarrow>\<^sub>e Aborts NameError" |
EvalLiteral: "\<rho>, ExprLiteral l \<Rightarrow>\<^sub>e Val (VLit l)" |
EvalLambda: "\<rho>, ExprLambda xs e \<Rightarrow>\<^sub>e Val Lam(\<rho>, xs, e)" |
EvalUnOp: "\<rho>, node e \<Rightarrow>\<^sub>e r \<Longrightarrow> \<rho>, ExprUnOp op e \<Rightarrow>\<^sub>e mlet r (unop_meaning op)" |
EvalBinOp: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val v ; \<rho>, node e' \<Rightarrow>\<^sub>e r \<rbrakk>
  \<Longrightarrow> \<rho>, ExprBinOp op e e' \<Rightarrow>\<^sub>e mlet r (binop_meaning op v)" |
EvalBinOpFail: "\<rho>, node e \<Rightarrow>\<^sub>e Aborts \<kappa> \<Longrightarrow> \<rho>, ExprBinOp op e e' \<Rightarrow>\<^sub>e Aborts \<kappa>" |
EvalAndFalse: "\<rho>, node e \<Rightarrow>\<^sub>e Val false \<Longrightarrow> \<rho>, ExprAnd e e' \<Rightarrow>\<^sub>e Val false" |
EvalAndTrue: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val true ; \<rho>, node e' \<Rightarrow>\<^sub>e r \<rbrakk> \<Longrightarrow> \<rho>, ExprAnd e e' \<Rightarrow>\<^sub>e r" |
EvalAndFail: "\<rho>, node e \<Rightarrow>\<^sub>e Aborts \<kappa> \<Longrightarrow> \<rho>, ExprAnd e e' \<Rightarrow>\<^sub>e Aborts \<kappa>" |
EvalAndNonBool: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val v ; v \<notin> {true, false} \<rbrakk> \<Longrightarrow> \<rho>, ExprAnd e e' \<Rightarrow>\<^sub>e Aborts Excluded" |
EvalOrTrue: "\<rho>, node e \<Rightarrow>\<^sub>e Val true \<Longrightarrow> \<rho>, ExprOr e e' \<Rightarrow>\<^sub>e Val true" |
EvalOrFalse: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val false ; \<rho>, node e' \<Rightarrow>\<^sub>e r \<rbrakk> \<Longrightarrow> \<rho>, ExprOr e e' \<Rightarrow>\<^sub>e r" |
EvalOrFail: "\<rho>, node e \<Rightarrow>\<^sub>e Aborts \<kappa> \<Longrightarrow> \<rho>, ExprOr e e' \<Rightarrow>\<^sub>e Aborts \<kappa>" |
EvalOrNonBool: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val v ; v \<notin> {true, false} \<rbrakk> \<Longrightarrow> \<rho>, ExprOr e e' \<Rightarrow>\<^sub>e Aborts Excluded" |
EvalCondTrue: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val true ; \<rho>, node e1 \<Rightarrow>\<^sub>e r \<rbrakk> \<Longrightarrow> \<rho>, ExprCond e1 e e2 \<Rightarrow>\<^sub>e r" |
EvalCondFalse: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val false ; \<rho>, node e2 \<Rightarrow>\<^sub>e r \<rbrakk> \<Longrightarrow> \<rho>, ExprCond e1 e e2 \<Rightarrow>\<^sub>e r" |
EvalCondFail: "\<rho>, node e \<Rightarrow>\<^sub>e Aborts \<kappa> \<Longrightarrow> \<rho>, ExprCond e1 e e2 \<Rightarrow>\<^sub>e Aborts \<kappa>" |
EvalCondNonBool: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val v ; v \<notin> {true, false} \<rbrakk> \<Longrightarrow> \<rho>, ExprCond e1 e e2 \<Rightarrow>\<^sub>e Aborts Excluded" |
EvalList: "\<rho>, es \<Rightarrow>\<^sub>e\<^sub>s Val vs \<Longrightarrow> \<rho>, ExprList es \<Rightarrow>\<^sub>e Val (VList vs)" |
EvalListFail: "\<rho>, es \<Rightarrow>\<^sub>e\<^sub>s Aborts \<kappa> \<Longrightarrow> \<rho>, ExprList es \<Rightarrow>\<^sub>e Aborts \<kappa>" |
EvalTuple: "\<rho>, es \<Rightarrow>\<^sub>e\<^sub>s Val vs \<Longrightarrow> \<rho>, ExprTuple es \<Rightarrow>\<^sub>e Val (VTuple vs)" |
EvalTupleFail: "\<rho>, es \<Rightarrow>\<^sub>e\<^sub>s Aborts \<kappa> \<Longrightarrow> \<rho>, ExprTuple es \<Rightarrow>\<^sub>e Aborts \<kappa>" |
EvalCallLambda:
  "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val Lam(\<rho>', xs, e')
  ; \<rho>, es \<Rightarrow>\<^sub>e\<^sub>s Val us
  ; length xs = length us
  ; \<rho>' \<otimes> fmap_of_list (zip xs us), node e' \<Rightarrow>\<^sub>e r
  \<rbrakk> \<Longrightarrow> \<rho>, ExprCall e (es, []) \<Rightarrow>\<^sub>e r" |
EvalCallLambdaArity:
  "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val Lam(\<rho>', xs, e')
  ; \<rho>, es \<Rightarrow>\<^sub>e\<^sub>s Val us
  ; length xs \<noteq> length us
  \<rbrakk> \<Longrightarrow> \<rho>, ExprCall e (es, []) \<Rightarrow>\<^sub>e Aborts TypeError" |
EvalCallDef:
  "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val Def(\<rho>', ds, j)
  ; node (ds ! j) = Def f \<alpha>s xps \<psi> s
  ; vs = map (\<lambda>i. Def(\<rho>', ds, i)) [0..<length ds]
  ; \<rho>, es \<Rightarrow>\<^sub>e\<^sub>s Val us
  ; length xps = length us
  ; scope VUnbound (map fst xps) s = Some \<rho>s
  ; \<rho>' \<otimes> fmap_of_list (zip (map (def_name \<circ> node) ds) vs) \<otimes> fmap_of_list (zip (map fst xps) us) \<otimes> \<rho>s,
      node s \<Rightarrow>\<^sub>s o
  \<rbrakk> \<Longrightarrow> \<rho>, ExprCall e (es, []) \<Rightarrow>\<^sub>e call_result o" |
EvalCallDefArity:
  "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val Def(\<rho>', ds, j)
  ; node (ds ! j) = Def f \<alpha>s xps \<psi> s
  ; \<rho>, es \<Rightarrow>\<^sub>e\<^sub>s Val us
  ; length xps \<noteq> length us
  \<rbrakk> \<Longrightarrow> \<rho>, ExprCall e (es, []) \<Rightarrow>\<^sub>e Aborts TypeError" |
EvalCallNonFun:
  "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val v ; \<rho>, es \<Rightarrow>\<^sub>e\<^sub>s Val us ; \<not> is_closure v \<rbrakk>
  \<Longrightarrow> \<rho>, ExprCall e (es, []) \<Rightarrow>\<^sub>e Aborts TypeError" |
EvalCallFail: "\<rho>, node e \<Rightarrow>\<^sub>e Aborts \<kappa> \<Longrightarrow> \<rho>, ExprCall e (es, []) \<Rightarrow>\<^sub>e Aborts \<kappa>" |
EvalCallFailArgs:
  "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val v ; \<rho>, es \<Rightarrow>\<^sub>e\<^sub>s Aborts \<kappa> \<rbrakk> \<Longrightarrow> \<rho>, ExprCall e (es, []) \<Rightarrow>\<^sub>e Aborts \<kappa>" |

EvalExprsNil: "\<rho>, [] \<Rightarrow>\<^sub>e\<^sub>s Val []" |
EvalExprsCons: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val v ; \<rho>, es \<Rightarrow>\<^sub>e\<^sub>s r \<rbrakk>
  \<Longrightarrow> \<rho>, e # es \<Rightarrow>\<^sub>e\<^sub>s mlet r (\<lambda>vs. Val (v # vs))" |
EvalExprsFail: "\<rho>, node e \<Rightarrow>\<^sub>e Aborts \<kappa> \<Longrightarrow> \<rho>, e # es \<Rightarrow>\<^sub>e\<^sub>s Aborts \<kappa>" |

EvalPass: "\<rho>, StmtPass \<Rightarrow>\<^sub>s Assigns \<epsilon>" |
EvalAssign: "\<rho>, node e \<Rightarrow>\<^sub>e r \<Longrightarrow> \<rho>, StmtAssign x \<pi> e \<Rightarrow>\<^sub>s mlet r (\<lambda>v. Assigns (fmupd x v \<epsilon>))" |
EvalExprStmt: "\<rho>, node e \<Rightarrow>\<^sub>e r \<Longrightarrow> \<rho>, StmtExpr e \<Rightarrow>\<^sub>s mlet r (\<lambda>v. Assigns \<epsilon>)" |
EvalReturn: "\<rho>, node e \<Rightarrow>\<^sub>e r \<Longrightarrow> \<rho>, StmtReturn (Some e) \<Rightarrow>\<^sub>s mlet r (\<lambda>v. Returns v)" |
EvalReturnNone: "\<rho>, StmtReturn None \<Rightarrow>\<^sub>s Returns (VLit LitNone)" |
EvalDefs:
  "vs = map (\<lambda>i. Def(\<rho>, ds, i)) [0..<length ds]
  \<Longrightarrow> \<rho>, StmtMutualRegion ds \<Rightarrow>\<^sub>s Assigns (fmap_of_list (zip (map (def_name \<circ> node) ds) vs))" |
EvalAssert: "\<rho>, node e \<Rightarrow>\<^sub>e Val true \<Longrightarrow> \<rho>, StmtAssert e None \<Rightarrow>\<^sub>s Assigns \<epsilon>" |
EvalAssertFalse: "\<rho>, node e \<Rightarrow>\<^sub>e Val false \<Longrightarrow> \<rho>, StmtAssert e None \<Rightarrow>\<^sub>s Aborts\<^sub>o (AssertionError None)" |
EvalAssertFail: "\<rho>, node e \<Rightarrow>\<^sub>e Aborts \<kappa> \<Longrightarrow> \<rho>, StmtAssert e None \<Rightarrow>\<^sub>s Aborts\<^sub>o \<kappa>" |
EvalAssertNonBool:
  "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val v ; v \<notin> {true, false} \<rbrakk> \<Longrightarrow> \<rho>, StmtAssert e None \<Rightarrow>\<^sub>s Aborts\<^sub>o Excluded" |
EvalAssertMsg: "\<rho>, node e \<Rightarrow>\<^sub>e Val true \<Longrightarrow> \<rho>, StmtAssert e (Some e') \<Rightarrow>\<^sub>s Assigns \<epsilon>" |
EvalAssertMsgFalse: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val false ; \<rho>, node e' \<Rightarrow>\<^sub>e Val (VLit (LitString w)) \<rbrakk>
  \<Longrightarrow> \<rho>, StmtAssert e (Some e') \<Rightarrow>\<^sub>s Aborts\<^sub>o (AssertionError (Some w))" |
EvalAssertMsgFalseFail: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val false ; \<rho>, node e' \<Rightarrow>\<^sub>e Aborts \<kappa> \<rbrakk>
  \<Longrightarrow> \<rho>, StmtAssert e (Some e') \<Rightarrow>\<^sub>s Aborts\<^sub>o \<kappa>" |
EvalAssertMsgFail: "\<rho>, node e \<Rightarrow>\<^sub>e Aborts \<kappa> \<Longrightarrow> \<rho>, StmtAssert e (Some e') \<Rightarrow>\<^sub>s Aborts\<^sub>o \<kappa>" |
EvalAssertMsgNonBool:
  "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val v ; v \<notin> {true, false} \<rbrakk> \<Longrightarrow> \<rho>, StmtAssert e (Some e') \<Rightarrow>\<^sub>s Aborts\<^sub>o Excluded" |
EvalAssertMsgNonStr:
  "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val false ; \<rho>, node e' \<Rightarrow>\<^sub>e Val v ; \<forall>w. v \<noteq> VLit (LitString w) \<rbrakk>
  \<Longrightarrow> \<rho>, StmtAssert e (Some e') \<Rightarrow>\<^sub>s Aborts\<^sub>o Excluded" |
EvalIfTrue: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val true ; \<rho>, node s \<Rightarrow>\<^sub>s o \<rbrakk>
  \<Longrightarrow> \<rho>, StmtIf e s elifs else' \<Rightarrow>\<^sub>s o" |
EvalIfFalse: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val false ; \<rho>, (elifs, else') \<Rightarrow>\<^sub>e\<^sub>l\<^sub>i\<^sub>f o \<rbrakk>
  \<Longrightarrow> \<rho>, StmtIf e s elifs else' \<Rightarrow>\<^sub>s o" |
EvalIfFail: "\<rho>, node e \<Rightarrow>\<^sub>e Aborts \<kappa> \<Longrightarrow> \<rho>, StmtIf e s elifs else' \<Rightarrow>\<^sub>s Aborts\<^sub>o \<kappa>" |
EvalIfNonBool:
  "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val v ; v \<notin> {true, false} \<rbrakk> \<Longrightarrow> \<rho>, StmtIf e s elifs else' \<Rightarrow>\<^sub>s Aborts\<^sub>o Excluded" |
EvalSeq: "\<lbrakk> \<rho>, node s \<Rightarrow>\<^sub>s Assigns \<rho>' ; \<rho> \<otimes> \<rho>', node s' \<Rightarrow>\<^sub>s o \<rbrakk>
  \<Longrightarrow> \<rho>, StmtSeq s s' \<Rightarrow>\<^sub>s Assigns \<rho>' \<otimes>\<^sub>o o" |
EvalSeqReturn: "\<rho>, node s \<Rightarrow>\<^sub>s Returns v \<Longrightarrow> \<rho>, StmtSeq s s' \<Rightarrow>\<^sub>s Returns v" |
EvalSeqFail: "\<rho>, node s \<Rightarrow>\<^sub>s Aborts\<^sub>o \<kappa> \<Longrightarrow> \<rho>, StmtSeq s s' \<Rightarrow>\<^sub>s Aborts\<^sub>o \<kappa>" |

EvalIfNone: "\<rho>, ([], None) \<Rightarrow>\<^sub>e\<^sub>l\<^sub>i\<^sub>f Assigns \<epsilon>" |
EvalElse: "\<rho>, node s \<Rightarrow>\<^sub>s o \<Longrightarrow> \<rho>, ([], Some s) \<Rightarrow>\<^sub>e\<^sub>l\<^sub>i\<^sub>f o" |
EvalElifTrue: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val true ; \<rho>, node s \<Rightarrow>\<^sub>s o \<rbrakk>
  \<Longrightarrow> \<rho>, ((e, s) # elifs, else') \<Rightarrow>\<^sub>e\<^sub>l\<^sub>i\<^sub>f o" |
EvalElifFalse: "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val false ; \<rho>, (elifs, else') \<Rightarrow>\<^sub>e\<^sub>l\<^sub>i\<^sub>f o \<rbrakk>
  \<Longrightarrow> \<rho>, ((e, s) # elifs, else') \<Rightarrow>\<^sub>e\<^sub>l\<^sub>i\<^sub>f o" |
EvalElifFail: "\<rho>, node e \<Rightarrow>\<^sub>e Aborts \<kappa> \<Longrightarrow> \<rho>, ((e, s) # elifs, else') \<Rightarrow>\<^sub>e\<^sub>l\<^sub>i\<^sub>f Aborts\<^sub>o \<kappa>" |
EvalElifNonBool:
  "\<lbrakk> \<rho>, node e \<Rightarrow>\<^sub>e Val v ; v \<notin> {true, false} \<rbrakk> \<Longrightarrow> \<rho>, ((e, s) # elifs, else') \<Rightarrow>\<^sub>e\<^sub>l\<^sub>i\<^sub>f Aborts\<^sub>o Excluded"

lemmas eval_induct = eval_expr_eval_exprs_eval_stmt_eval_elif.inducts

end
