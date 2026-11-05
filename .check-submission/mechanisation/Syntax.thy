(* Abstract syntax and syntactic analyses *)
theory Syntax
  imports Complex_Main Util Floats Strings Positions
begin

type_synonym name = "var nonempty"

datatype lit =
    LitInt int
  | LitFloat float
  | LitString str
  | LitBool bool
  | LitNone

type_synonym 'u args = "'u list \<times> (var \<times> 'u) list"

datatype pat =
    PatLiteral lit
  | PatVar var
  | PatWildcard
  | PatList "pat located list"
  | PatTuple "pat located list"
  | PatConstr name "pat located args"
  | PatDict "(str \<times> pat located) list"
  | PatAs "pat located" var

datatype bop =
    BOpBitOr
  | BOpEq
  | BOpNeq
  | BOpLt
  | BOpLeq
  | BOpGt
  | BOpGeq
  | BOpAdd
  | BOpSub
  | BOpMul
  | BOpDiv
  | BOpFloorDiv
  | BOpMod
  | BOpPow
  | BOpIn
  | BOpNotIn

datatype uop = UOpNot | UOpPos | UOpNeg

datatype expr =
    ExprVar var
  | ExprLiteral lit
  | ExprCall "expr located" "expr located args"
  | ExprDict "(expr located \<times> expr located) list"
  | ExprAttribute "expr located" var
  | ExprSubscript "expr located" "expr located"
  | ExprBinOp bop "expr located" "expr located"
  | ExprUnOp uop "expr located"
  | ExprAnd "expr located" "expr located"
  | ExprOr "expr located" "expr located"
  | ExprCond "expr located" "expr located" "expr located"
  | ExprList "expr located list"
  | ExprTuple "expr located list"
  | ExprListComp "expr located" "qualifier located list"
  | ExprDictComp "expr located" "expr located" "qualifier located list"
  | ExprLambda "var list" "expr located"
and qualifier =
    Guard "expr located"
  | Generator var "expr located"

datatype prim_ty =
    object
  | Never
  | NoneType
  | bool
  | int
  | float
  | str
  | Sized

datatype ty_expr =
    TyExprPrim prim_ty
  | TyExprList ty_expr
  | TyExprTuple "ty_expr list"
  | TyExprDict ty_expr
  | TyExprCallable "ty_expr list" ty_expr
  | TyExprLiteral lit
  | TyExprName name "ty_expr list"
  | TyExprUnion ty_expr ty_expr

datatype ty =
    TyPrim prim_ty
  | TyList ty
  | TyTuple "ty list"
  | TyDict ty
  | TyCallable "ty list" ty
  | TyLiteral lit
  | TyVar var
  | TyClass name "ty list"
  | TyUnion ty ty

datatype sequence_kind = TupleKind | ListKind | RangeKind

datatype ty_scheme = TyScheme "var list" ty

datatype field_scheme = FieldScheme "var list" "(var \<times> ty) list"

datatype import =
    Import name
  | FromImport name "var list"

(* Two spec forms differing only in an omitted component share a constructor, with an option for the
   component. A dataclass always has a field list; an empty field list is written `pass` *)
datatype stmt =
    StmtPass
  | StmtSeq "stmt located" "stmt located"
  | StmtDeclare var ty_expr
  | StmtAssign var "ty_expr option" "expr located"
  | StmtExpr "expr located"
  | StmtAssert "expr located" "expr located option"
  | StmtReturn "expr located option"
  | StmtIf "expr located" "stmt located" "(expr located \<times> stmt located) list" "stmt located option"
  | StmtMatch "expr located" "(pat located \<times> stmt located) list"
  | StmtMutualRegion "func located list"
and func = Def var "var list" "(var \<times> ty_expr) list" ty_expr "stmt located"

type_synonym fields = "(var \<times> ty_expr) list"

datatype type_def =
    Dataclass var "var list" "(name \<times> ty_expr list) option" fields
  | TypeStmt var "var list" ty_expr

datatype top_stmt =
    Stmt "stmt located"
  | TopSeq top_stmt top_stmt
  | TypeDefs "type_def located list"

datatype module_body = ModuleBody "import located list" top_stmt

fun prefix_of :: "name \<Rightarrow> name \<Rightarrow> bool" (infix "\<preceq>" 50)
where
"(y, ys) \<preceq> (y', ys') = (y = y' \<and> take (length ys) ys' = ys)"

definition proper_prefix_of :: "name \<Rightarrow> name \<Rightarrow> bool" (infix "\<prec>" 50)
where
"q \<prec> q' = (q \<preceq> q' \<and> q \<noteq> q')"

(* Shortest first *)
fun proper_prefixes :: "name \<Rightarrow> name list"
where
"proper_prefixes (y, ys) = map (\<lambda>i. (y, take i ys)) [0..<length ys]"

definition unique_to :: "name \<Rightarrow> name \<Rightarrow> name list"
where
"unique_to q' q = filter (\<lambda>p. \<not> p \<preceq> q) (proper_prefixes q')"

definition builtins :: name where "builtins = (var ''builtins'', [])"
definition main :: name where "main = (var ''__main__'', [])"

fun def_name :: "func \<Rightarrow> var"
where
"def_name (Def f _ _ _ _) = f"

fun type_def_name :: "type_def \<Rightarrow> var"
where
"type_def_name (Dataclass c _ _ _) = c" |
"type_def_name (TypeStmt x _ _) = x"

fun binds_pat :: "pat \<Rightarrow> var set"
where
"binds_pat (PatVar x) = {x}" |
"binds_pat (PatAs p x) = binds_pat (node p) \<union> {x}" |
"binds_pat (PatList ps) = \<Union> (set (map (binds_pat \<circ> node) ps))" |
"binds_pat (PatTuple ps) = \<Union> (set (map (binds_pat \<circ> node) ps))" |
"binds_pat (PatConstr q (ps, kps)) =
  \<Union> (set (map (binds_pat \<circ> node) ps)) \<union> \<Union> (set (map (binds_pat \<circ> node \<circ> snd) kps))" |
"binds_pat (PatDict kps) = \<Union> (set (map (binds_pat \<circ> node \<circ> snd) kps))" |
"binds_pat _ = {}"

(* Variables bound by the patterns of the match statements in s, each at the position of its match statement,
   in order and with repeats *)
fun pat_bound_stmt :: "stmt located \<Rightarrow> var located list"
where
"pat_bound_stmt (At _ (StmtSeq s s')) = pat_bound_stmt s @ pat_bound_stmt s'" |
"pat_bound_stmt (At _ (StmtIf _ s elifs else')) =
  pat_bound_stmt s @ concat (map (\<lambda>(_, s'). pat_bound_stmt s') elifs)
  @ (case else' of None \<Rightarrow> [] | Some s' \<Rightarrow> pat_bound_stmt s')" |
"pat_bound_stmt (At p (StmtMatch _ cases)) =
  concat (map (\<lambda>(q, s). map (At p) (sorted_list_of_set (binds_pat (node q))) @ pat_bound_stmt s) cases)" |
"pat_bound_stmt _ = []"

fun pat_bound_top :: "top_stmt \<Rightarrow> var located list"
where
"pat_bound_top (Stmt s) = pat_bound_stmt s" |
"pat_bound_top (TopSeq t t') = pat_bound_top t @ pat_bound_top t'" |
"pat_bound_top (TypeDefs \<chi>s) = []"

definition binds_stmt :: "stmt located \<Rightarrow> var set"
where
"binds_stmt s = set (map node (pat_bound_stmt s))"

fun binds_quals :: "qualifier located list \<Rightarrow> var set"
where
"binds_quals [] = {}" |
"binds_quals (At _ (Guard _) # gs) = binds_quals gs" |
"binds_quals (At _ (Generator x _) # gs) = {x} \<union> binds_quals gs"

definition binds_top :: "top_stmt \<Rightarrow> var set"
where
"binds_top t = set (map node (pat_bound_top t))"

fun assigns_stmt :: "stmt \<Rightarrow> var set"
where
"assigns_stmt (StmtDeclare x _) = {x}" |
"assigns_stmt (StmtAssign x _ _) = {x}" |
"assigns_stmt (StmtSeq s s') = assigns_stmt (node s) \<union> assigns_stmt (node s')" |
"assigns_stmt (StmtMutualRegion ds) = set (map (def_name \<circ> node) ds)" |
"assigns_stmt (StmtIf _ s elifs else') =
  assigns_stmt (node s) \<union> \<Union> (set (map (\<lambda>(_, s'). assigns_stmt (node s')) elifs))
  \<union> (case else' of None \<Rightarrow> {} | Some s' \<Rightarrow> assigns_stmt (node s'))" |
"assigns_stmt (StmtMatch _ cases) =
  \<Union> (set (map (\<lambda>(p, s). binds_pat (node p) \<union> assigns_stmt (node s)) cases))" |
"assigns_stmt _ = {}"

fun assigns_top :: "top_stmt \<Rightarrow> var set"
where
"assigns_top (Stmt s) = assigns_stmt (node s)" |
"assigns_top (TopSeq t t') = assigns_top t \<union> assigns_top t'" |
"assigns_top (TypeDefs \<chi>s) = set (map (type_def_name \<circ> node) \<chi>s)"

(* Names declared in s, each at the position of its declaring statement, in order and with repeats *)
fun declarations_stmt :: "stmt located \<Rightarrow> var located list"
where
"declarations_stmt (At p (StmtDeclare x _)) = [At p x]" |
"declarations_stmt (At p (StmtAssign x (Some _) _)) = [At p x]" |
"declarations_stmt (At _ (StmtSeq s s')) = declarations_stmt s @ declarations_stmt s'" |
"declarations_stmt (At _ (StmtMutualRegion ds)) = map (\<lambda>d. At (pos_of d) (def_name (node d))) ds" |
"declarations_stmt (At _ (StmtIf _ s elifs else')) =
  declarations_stmt s @ concat (map (\<lambda>(_, s'). declarations_stmt s') elifs)
  @ (case else' of None \<Rightarrow> [] | Some s' \<Rightarrow> declarations_stmt s')" |
"declarations_stmt (At _ (StmtMatch _ cases)) = concat (map (\<lambda>(_, s). declarations_stmt s) cases)" |
"declarations_stmt _ = []"

(* Names bound by imports, each at the position of its import, the root of a plain import listed once *)
fun declarations_imports :: "import located list \<Rightarrow> var located list"
where
"declarations_imports [] = []" |
"declarations_imports (At p (Import (x, xs)) # \<iota>s) =
  (if list_ex (\<lambda>\<iota>. case node \<iota> of Import (x', _) \<Rightarrow> x' = x | _ \<Rightarrow> False) \<iota>s then declarations_imports \<iota>s
   else At p x # declarations_imports \<iota>s)" |
"declarations_imports (At p (FromImport q xs) # \<iota>s) = map (At p) xs @ declarations_imports \<iota>s"

fun declarations_top :: "top_stmt \<Rightarrow> var located list"
where
"declarations_top (Stmt s) = declarations_stmt s" |
"declarations_top (TopSeq t t') = declarations_top t @ declarations_top t'" |
"declarations_top (TypeDefs \<chi>s) = map (\<lambda>\<chi>. At (pos_of \<chi>) (type_def_name (node \<chi>))) \<chi>s"

definition declares_stmt :: "stmt \<Rightarrow> var list"
where
"declares_stmt s = map node (declarations_stmt (At no_pos s))"

definition declares_imports :: "import located list \<Rightarrow> var list"
where
"declares_imports \<iota>s = map node (declarations_imports \<iota>s)"

definition declares_top :: "top_stmt \<Rightarrow> var list"
where
"declares_top t = map node (declarations_top t)"

(* Position of the last statement *)
fun last_pos :: "top_stmt \<Rightarrow> pos"
where
"last_pos (Stmt s) = pos_of s" |
"last_pos (TopSeq _ t) = last_pos t" |
"last_pos (TypeDefs \<chi>s) = pos_of (last \<chi>s)"

fun fv_expr :: "expr \<Rightarrow> var set" and fv_quals :: "qualifier located list \<Rightarrow> var set"
where
"fv_expr (ExprVar x) = {x}" |
"fv_expr (ExprLiteral _) = {}" |
"fv_expr (ExprCall e (es, kws)) =
  fv_expr (node e) \<union> \<Union> (set (map (fv_expr \<circ> node) es)) \<union> \<Union> (set (map (fv_expr \<circ> node \<circ> snd) kws))" |
"fv_expr (ExprDict kvs) =
  \<Union> (set (map (fv_expr \<circ> node \<circ> fst) kvs)) \<union> \<Union> (set (map (fv_expr \<circ> node \<circ> snd) kvs))" |
"fv_expr (ExprAttribute e _) = fv_expr (node e)" |
"fv_expr (ExprSubscript e e') = fv_expr (node e) \<union> fv_expr (node e')" |
"fv_expr (ExprBinOp _ e e') = fv_expr (node e) \<union> fv_expr (node e')" |
"fv_expr (ExprUnOp _ e) = fv_expr (node e)" |
"fv_expr (ExprAnd e e') = fv_expr (node e) \<union> fv_expr (node e')" |
"fv_expr (ExprOr e e') = fv_expr (node e) \<union> fv_expr (node e')" |
"fv_expr (ExprCond e\<^sub>1 e e\<^sub>2) = fv_expr (node e\<^sub>1) \<union> fv_expr (node e) \<union> fv_expr (node e\<^sub>2)" |
"fv_expr (ExprList es) = \<Union> (set (map (fv_expr \<circ> node) es))" |
"fv_expr (ExprTuple es) = \<Union> (set (map (fv_expr \<circ> node) es))" |
"fv_expr (ExprListComp e gs) = fv_quals gs \<union> (fv_expr (node e) - binds_quals gs)" |
"fv_expr (ExprDictComp e e' gs) = fv_quals gs \<union> ((fv_expr (node e) \<union> fv_expr (node e')) - binds_quals gs)" |
"fv_expr (ExprLambda xs e) = fv_expr (node e) - set xs" |

"fv_quals [] = {}" |
"fv_quals (At _ (Guard e) # gs) = fv_expr (node e) \<union> fv_quals gs" |
"fv_quals (At _ (Generator x e) # gs) = fv_expr (node e) \<union> (fv_quals gs - {x})"

fun fv_ty :: "ty \<Rightarrow> var set"
where
"fv_ty (TyVar \<alpha>) = {\<alpha>}" |
"fv_ty (TyList \<tau>) = fv_ty \<tau>" |
"fv_ty (TyDict \<tau>) = fv_ty \<tau>" |
"fv_ty (TyTuple \<tau>s) = \<Union> (set (map fv_ty \<tau>s))" |
"fv_ty (TyCallable \<sigma>s \<tau>) = \<Union> (set (map fv_ty \<sigma>s)) \<union> fv_ty \<tau>" |
"fv_ty (TyClass _ \<tau>s) = \<Union> (set (map fv_ty \<tau>s))" |
"fv_ty (TyUnion \<sigma> \<tau>) = fv_ty \<sigma> \<union> fv_ty \<tau>" |
"fv_ty _ = {}"

fun subterms :: "ty \<Rightarrow> ty list"
where
"subterms (TyUnion \<sigma> \<tau>) = subterms \<sigma> @ subterms \<tau>" |
"subterms (TyList \<tau>) = TyList \<tau> # subterms \<tau>" |
"subterms (TyDict \<tau>) = TyDict \<tau> # subterms \<tau>" |
"subterms (TyTuple \<tau>s) = TyTuple \<tau>s # concat (map subterms \<tau>s)" |
"subterms (TyCallable \<tau>s \<tau>) = TyCallable \<tau>s \<tau> # concat (map subterms \<tau>s) @ subterms \<tau>" |
"subterms (TyClass C \<tau>s) = TyClass C \<tau>s # concat (map subterms \<tau>s)" |
"subterms \<tau> = [\<tau>]"

fun captures_expr :: "expr \<Rightarrow> var set" and captures_quals :: "qualifier located list \<Rightarrow> var set"
where
"captures_expr (ExprVar _) = {}" |
"captures_expr (ExprLiteral _) = {}" |
"captures_expr (ExprCall e (es, kws)) =
  captures_expr (node e) \<union> \<Union> (set (map (captures_expr \<circ> node) es))
  \<union> \<Union> (set (map (captures_expr \<circ> node \<circ> snd) kws))" |
"captures_expr (ExprDict kvs) =
  \<Union> (set (map (captures_expr \<circ> node \<circ> fst) kvs)) \<union> \<Union> (set (map (captures_expr \<circ> node \<circ> snd) kvs))" |
"captures_expr (ExprAttribute e _) = captures_expr (node e)" |
"captures_expr (ExprSubscript e e') = captures_expr (node e) \<union> captures_expr (node e')" |
"captures_expr (ExprBinOp _ e e') = captures_expr (node e) \<union> captures_expr (node e')" |
"captures_expr (ExprUnOp _ e) = captures_expr (node e)" |
"captures_expr (ExprAnd e e') = captures_expr (node e) \<union> captures_expr (node e')" |
"captures_expr (ExprOr e e') = captures_expr (node e) \<union> captures_expr (node e')" |
"captures_expr (ExprCond e\<^sub>1 e e\<^sub>2) =
  captures_expr (node e\<^sub>1) \<union> captures_expr (node e) \<union> captures_expr (node e\<^sub>2)" |
"captures_expr (ExprList es) = \<Union> (set (map (captures_expr \<circ> node) es))" |
"captures_expr (ExprTuple es) = \<Union> (set (map (captures_expr \<circ> node) es))" |
"captures_expr (ExprListComp e gs) = captures_quals gs \<union> (captures_expr (node e) - binds_quals gs)" |
"captures_expr (ExprDictComp e e' gs) =
  captures_quals gs \<union> ((captures_expr (node e) \<union> captures_expr (node e')) - binds_quals gs)" |
"captures_expr (ExprLambda xs e) = fv_expr (node e) - set xs" |

"captures_quals [] = {}" |
"captures_quals (At _ (Guard e) # gs) = captures_expr (node e) \<union> captures_quals gs" |
"captures_quals (At _ (Generator x e) # gs) = captures_expr (node e) \<union> (captures_quals gs - {x})"

(* u marks a variable unbound: the value or the context entry *)
definition scope_stmt :: "'a \<Rightarrow> var list \<Rightarrow> stmt located \<Rightarrow> (var, 'a) fmap option"
where
"scope_stmt u ys s =
  (if distinct ys \<and> distinct (declares_stmt (node s)) \<and> set ys \<inter> set (declares_stmt (node s)) = {}
      \<and> set ys \<inter> binds_stmt s = {} \<and> set (declares_stmt (node s)) \<inter> binds_stmt s = {}
   then Some (fmconst (assigns_stmt (node s) - set ys) u)
   else None)"

definition scope_top :: "'a \<Rightarrow> var list \<Rightarrow> top_stmt \<Rightarrow> (var, 'a) fmap option"
where
"scope_top u ys t =
  (if distinct ys \<and> distinct (declares_top t) \<and> set ys \<inter> set (declares_top t) = {} \<and> set ys \<inter> binds_top t = {}
      \<and> set (declares_top t) \<inter> binds_top t = {}
   then Some (fmconst (assigns_top t - set ys) u)
   else None)"

fun prim_name :: "prim_ty \<Rightarrow> var"
where
"prim_name object = var ''object''" |
"prim_name Never = var ''Never''" |
"prim_name NoneType = var ''None''" |
"prim_name bool = var ''bool''" |
"prim_name int = var ''int''" |
"prim_name float = var ''float''" |
"prim_name str = var ''str''" |
"prim_name Sized = var ''Sized''"

fun numeric_literal :: "expr \<Rightarrow> bool"
where
"numeric_literal (ExprLiteral (LitInt _)) = True" |
"numeric_literal (ExprLiteral (LitFloat _)) = True" |
"numeric_literal _ = False"

fun short_name :: "name \<Rightarrow> var"
where
"short_name (x, xs) = (if xs = [] then x else last xs)"

fun lambda_of :: "expr \<Rightarrow> (var list \<times> expr located) option"
where
"lambda_of (ExprLambda xs e) = Some (xs, e)" |
"lambda_of _ = None"

lemma lambda_of_size: "lambda_of e = Some (xs, e') \<Longrightarrow> size (node e') < size e"
  by (cases e) auto

fun dotted_name :: "expr \<Rightarrow> name option"
where
"dotted_name (ExprVar x) = Some (x, [])" |
"dotted_name (ExprAttribute e x) = map_option (\<lambda>q. snoc q x) (dotted_name (node e))" |
"dotted_name _ = None"

(* Targets of the plain assignments in s, each at the position of its assignment, in order *)
fun assign_targets_stmt :: "stmt located \<Rightarrow> var located list"
where
"assign_targets_stmt (At p (StmtAssign x None _)) = [At p x]" |
"assign_targets_stmt (At _ (StmtSeq s s')) = assign_targets_stmt s @ assign_targets_stmt s'" |
"assign_targets_stmt (At _ (StmtIf _ s elifs else')) =
  assign_targets_stmt s @ concat (map (\<lambda>(_, s'). assign_targets_stmt s') elifs)
  @ (case else' of None \<Rightarrow> [] | Some s' \<Rightarrow> assign_targets_stmt s')" |
"assign_targets_stmt (At _ (StmtMatch _ cases)) = concat (map (\<lambda>(_, s). assign_targets_stmt s) cases)" |
"assign_targets_stmt _ = []"

fun assign_targets_top :: "top_stmt \<Rightarrow> var located list"
where
"assign_targets_top (Stmt s) = assign_targets_stmt s" |
"assign_targets_top (TopSeq t t') = assign_targets_top t @ assign_targets_top t'" |
"assign_targets_top (TypeDefs _) = []"

(* Names bound by imports, each at the position of its import, in order and with repeats *)
fun binders_imports :: "import located list \<Rightarrow> var located list"
where
"binders_imports [] = []" |
"binders_imports (At p (Import (x, _)) # \<iota>s) = At p x # binders_imports \<iota>s" |
"binders_imports (At p (FromImport _ xs) # \<iota>s) = map (At p) xs @ binders_imports \<iota>s"

(* Names assigned by the top-level statements of t, each at the position of its statement, in order and with
   repeats *)
fun binders_top :: "top_stmt \<Rightarrow> var located list"
where
"binders_top (Stmt s) = map (At (pos_of s)) (sorted_list_of_set (assigns_stmt (node s)))" |
"binders_top (TopSeq t t') = binders_top t @ binders_top t'" |
"binders_top (TypeDefs \<chi>s) = map (\<lambda>\<chi>. At (pos_of \<chi>) (type_def_name (node \<chi>))) \<chi>s"

(* Position of the first import or top-level statement binding x *)
definition binder_pos :: "import located list \<Rightarrow> top_stmt \<Rightarrow> var \<Rightarrow> pos"
where
"binder_pos \<iota>s t x = pos_of (the (find (\<lambda>y. node y = x) (binders_imports \<iota>s @ binders_top t)))"

definition prim_of_name :: "var \<Rightarrow> prim_ty option"
where
"prim_of_name x = find (\<lambda>\<nu>. prim_name \<nu> = x) [object, Never, NoneType, bool, int, float, str, Sized]"

(* Arguments of a subscript *)
fun subscript_args :: "expr located \<Rightarrow> expr located list"
where
"subscript_args (At _ (ExprTuple es)) = es" |
"subscript_args e = [e]"

(* Type expression denoted by an expression *)
fun type_expr_of :: "expr located \<Rightarrow> ty_expr option"
where
"type_expr_of (At _ (ExprLiteral LitNone)) = Some (TyExprPrim NoneType)" |
"type_expr_of (At _ (ExprVar x)) =
  Some (case prim_of_name x of Some \<nu> \<Rightarrow> TyExprPrim \<nu> | None \<Rightarrow> TyExprName (x, []) [])" |
"type_expr_of (At _ (ExprAttribute e x)) = map_option (\<lambda>q. TyExprName q []) (dotted_name (ExprAttribute e x))" |
"type_expr_of (At _ (ExprBinOp BOpBitOr e e')) = do {
   \<psi> \<leftarrow> type_expr_of e; \<psi>' \<leftarrow> type_expr_of e'; Some (TyExprUnion \<psi> \<psi>')
 }" |
"type_expr_of (At _ (ExprSubscript e e')) =
  (let head = (case node e of ExprVar x \<Rightarrow> Some x | _ \<Rightarrow> None) in
   if head = Some (var ''Literal'') then
     (case node e' of
        ExprLiteral (LitFloat _) \<Rightarrow> None
      | ExprLiteral l \<Rightarrow> Some (TyExprLiteral l)
      | _ \<Rightarrow> None)
   else if head = Some (var ''Callable'') then
     (case e' of
        At _ (ExprTuple [At _ (ExprList es), e'']) \<Rightarrow> do {
          \<psi>s \<leftarrow> those (map type_expr_of es); \<psi> \<leftarrow> type_expr_of e''; Some (TyExprCallable \<psi>s \<psi>)
        }
      | _ \<Rightarrow> None)
   else do {
     \<psi>s \<leftarrow> those (case e' of At _ (ExprTuple es) \<Rightarrow> map type_expr_of es | _ \<Rightarrow> [type_expr_of e']);
     if head = Some (var ''list'') then (case \<psi>s of [\<psi>] \<Rightarrow> Some (TyExprList \<psi>) | _ \<Rightarrow> None)
     else if head = Some (var ''tuple'') then Some (TyExprTuple \<psi>s)
     else if head = Some (var ''dict'')
     then (case \<psi>s of [TyExprPrim str, \<psi>] \<Rightarrow> Some (TyExprDict \<psi>) | _ \<Rightarrow> None)
     else map_option (\<lambda>q. TyExprName q \<psi>s) (dotted_name (node e))
   })" |
"type_expr_of _ = None"

consts
  binds :: "'a \<Rightarrow> var set"
  assigns :: "'a \<Rightarrow> var set"
  declares :: "'a \<Rightarrow> var list"
  declarations :: "'a \<Rightarrow> var located list"
  pat_bound :: "'a \<Rightarrow> var located list"
  fv :: "'a \<Rightarrow> var set"
  captures :: "'a \<Rightarrow> var set"
  assign_targets :: "'a \<Rightarrow> var located list"
  scope :: "'u \<Rightarrow> 'y \<Rightarrow> 'a \<Rightarrow> (var, 'u) fmap option"

adhoc_overloading binds \<rightleftharpoons> binds_pat binds_stmt binds_quals binds_top
adhoc_overloading assigns \<rightleftharpoons> assigns_stmt assigns_top
adhoc_overloading declares \<rightleftharpoons> declares_stmt declares_top declares_imports
adhoc_overloading declarations \<rightleftharpoons> declarations_stmt declarations_top declarations_imports
adhoc_overloading pat_bound \<rightleftharpoons> pat_bound_stmt pat_bound_top
adhoc_overloading fv \<rightleftharpoons> fv_expr fv_quals fv_ty
adhoc_overloading captures \<rightleftharpoons> captures_expr captures_quals
adhoc_overloading assign_targets \<rightleftharpoons> assign_targets_stmt assign_targets_top
adhoc_overloading scope \<rightleftharpoons> scope_stmt scope_top

end
