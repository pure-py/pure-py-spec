(* Static outcomes; typing of expressions, statements and type definitions *)
theory Typing
  imports Operators Matching
begin

(* Type at which a variable is bound or declared *)
fun var_ty :: "cxt_entry \<Rightarrow> ty option"
where
"var_ty (Ty \<tau>) = Some \<tau>" |
"var_ty (DU \<tau>) = Some \<tau>" |
"var_ty (PU \<tau> _) = Some \<tau>" |
"var_ty _ = None"

(* Type scheme at which a variable is bound or declared *)
fun scheme_of :: "cxt_entry \<Rightarrow> ty_scheme option"
where
"scheme_of (Scheme \<pi>) = Some \<pi>" |
"scheme_of (PUScheme \<pi> _) = Some \<pi>" |
"scheme_of _ = None"

(* Merge of a context entry with undefined, flagged if the variable is declared in a branch *)
fun possibly_unassigned :: "bool \<Rightarrow> cxt_entry \<Rightarrow> cxt_entry"
where
"possibly_unassigned b (Ty \<tau>) = PU \<tau> b" |
"possibly_unassigned b (DU \<tau>) = PU \<tau> b" |
"possibly_unassigned b (PU \<tau> _) = PU \<tau> b" |
"possibly_unassigned b (Scheme \<pi>) = PUScheme \<pi> b" |
"possibly_unassigned b (PUScheme \<pi> _) = PUScheme \<pi> b" |
"possibly_unassigned _ _ = undefined"

fun merge_cxt_entry :: "class_table \<Rightarrow> bool \<Rightarrow> cxt_entry option \<Rightarrow> cxt_entry option \<Rightarrow> cxt_entry"
where
"merge_cxt_entry \<Sigma> b (Some (Ty \<sigma>)) (Some (Ty \<tau>)) = Ty (\<sigma> \<squnion>\<^bsub>\<Sigma>\<^esub> \<tau>)" |
"merge_cxt_entry \<Sigma> b (Some \<theta>) (Some \<theta>') =
  (if \<theta> = \<theta>' then \<theta>
   else case (scheme_of \<theta>, scheme_of \<theta>', var_ty \<theta>, var_ty \<theta>') of
     (Some \<pi>, Some \<pi>', _, _) \<Rightarrow> if \<pi> = \<pi>' then PUScheme \<pi> b else undefined
   | (None, None, Some \<sigma>, Some \<tau>) \<Rightarrow> PU (\<sigma> \<squnion>\<^bsub>\<Sigma>\<^esub> \<tau>) b
   | _ \<Rightarrow> undefined)" |
"merge_cxt_entry \<Sigma> b (Some \<theta>) None = possibly_unassigned b \<theta>" |
"merge_cxt_entry \<Sigma> b None (Some \<theta>) = possibly_unassigned b \<theta>" |
"merge_cxt_entry \<Sigma> b None None = undefined"

(* Merge of the contexts of two branches of a statement declaring the variables D *)
definition merge :: "class_table \<Rightarrow> var set \<Rightarrow> cxt \<Rightarrow> cxt \<Rightarrow> cxt"
where
"merge \<Sigma> D \<Gamma> \<Gamma>' =
  fmmap_keys (\<lambda>x _. merge_cxt_entry \<Sigma> (x \<in> D) (fmlookup \<Gamma> x) (fmlookup \<Gamma>' x)) (\<Gamma> \<otimes> \<Gamma>')"

(* Assigns\<^sub>R \<Delta> r: the statement can complete normally, adding bindings \<Delta>. If present, r is the error reported
   when a function body ends with a statement which OurLang determines to return or raise but which mypy treats
   as completing normally. *)
datatype static_outcome = Assigns\<^sub>R cxt "reason option" | Returns\<^sub>R

fun merge_outcome :: "class_table \<Rightarrow> var set \<Rightarrow> static_outcome \<Rightarrow> static_outcome \<Rightarrow> static_outcome"
where
"merge_outcome \<Sigma> D (Assigns\<^sub>R \<Delta> r) (Assigns\<^sub>R \<Delta>' r') =
  Assigns\<^sub>R (merge \<Sigma> D \<Delta> \<Delta>') (if r' = None then None else r)" |
"merge_outcome \<Sigma> D R Returns\<^sub>R = R" |
"merge_outcome \<Sigma> D Returns\<^sub>R R = R"

definition merges :: "class_table \<Rightarrow> var set \<Rightarrow> static_outcome may_fail list \<Rightarrow> static_outcome may_fail"
where
"merges \<Sigma> D ms = do { Rs \<leftarrow> those_sum ms; Ok (foldr (merge_outcome \<Sigma> D) Rs Returns\<^sub>R) }"

fun override_outcome :: "static_outcome \<Rightarrow> static_outcome \<Rightarrow> static_outcome" (infixl "\<otimes>\<^sub>R" 100)
where
"Assigns\<^sub>R \<Delta> r \<otimes>\<^sub>R Assigns\<^sub>R \<Delta>' r' = Assigns\<^sub>R (\<Delta> \<otimes> \<Delta>') (if r = None then r' else None)" |
"_ \<otimes>\<^sub>R _ = Returns\<^sub>R"

definition attr_module :: "name \<Rightarrow> cxt \<Rightarrow> var \<Rightarrow> name \<Rightarrow> ty may_fail"
where
"attr_module q \<Gamma> x q' =
  (case fmlookup \<Gamma> x of
     None \<Rightarrow> Fail (UnknownMember x q)
   | Some (Ty \<tau>) \<Rightarrow> Ok \<tau>
   | Some (ModStub q'') \<Rightarrow> Fail (SubmoduleNotImported q'')
   | Some (ModChecked _ _) \<Rightarrow> Fail (ModuleAsValue q')
   | Some (Type _) \<Rightarrow> Fail (ClassAsValue q')
   | Some (TypeAlias _ _ _ _) \<Rightarrow> Fail (TypeAliasAsValue q')
   | Some PredefName \<Rightarrow> Fail (PredefinedNameAsValue q')
   | Some (Scheme _) \<Rightarrow> Fail (TypeSchemeAsValue q')
   | Some TypeVar \<Rightarrow> undefined
   | Some _ \<Rightarrow> Fail (UnassignedMember x q))"

(* Type of attribute x of e when e is a dotted name resolving to a module; None otherwise *)
definition module_attribute :: "cxt \<Rightarrow> expr \<Rightarrow> var \<Rightarrow> ty may_fail option"
where
"module_attribute \<Gamma> e x = do {
   q \<leftarrow> dotted_name e;
   case lookup \<Gamma> q of
     Some (ModChecked q' \<Gamma>') \<Rightarrow> Some (attr_module q' \<Gamma>' x (snoc q x))
   | Some (ModStub q') \<Rightarrow> Some (Fail (SubmoduleNotImported q'))
   | _ \<Rightarrow> None
 }"

(* Context binding parameters xs at \<tau>s *)
definition params_cxt :: "var list \<Rightarrow> ty list \<Rightarrow> cxt may_fail"
where
"params_cxt xs \<tau>s = (if distinct xs then Ok (fmap_of_list (zip xs (map Ty \<tau>s))) else Fail undefined)"

(* Failure if one of the variables bound by qualifiers gs, with bindings \<Delta>, is in X, the variables captured by
   lambdas, located at the first generator *)
definition captured :: "qualifier located list \<Rightarrow> var set \<Rightarrow> cxt \<Rightarrow> unit may_fail"
where
"captured gs X \<Delta> =
  (let Y = X \<inter> fset (fmdom \<Delta>) in
   if Y = {} then Ok () else Fail (Located (pos_of (hd gs)) (CapturedGeneratorVariable (Min Y))))"

definition lambda_args ::
  "var list \<Rightarrow> (var \<times> expr located) list \<Rightarrow> expr located list \<Rightarrow> ty may_fail list \<Rightarrow> cxt may_fail"
where
"lambda_args xs kws es \<sigma>s = do {
   ensure (kws = []) KeywordArgumentsNotConstructor;
   ensure (length xs = length es) (CallArityMismatch (length xs) (length es));
   \<tau>s \<leftarrow> those_sum \<sigma>s;
   params_cxt xs \<tau>s
 }"

(* Check of a name bound at a type scheme against \<tau>; None for other expressions *)
definition var_scheme :: "class_table \<Rightarrow> cxt \<Rightarrow> expr \<Rightarrow> ty \<Rightarrow> unit may_fail option"
where
"var_scheme \<Sigma> \<Gamma> e \<tau> =
  (case scheme_of_name \<Gamma> e of
     Some (TyScheme \<alpha>s \<sigma>) \<Rightarrow> Some (do {
       \<tau>s \<leftarrow> type_args_of (type_args \<Sigma> \<alpha>s \<sigma> \<tau>) \<alpha>s;
       let \<sigma>' = subst \<tau>s \<alpha>s \<sigma>;
       ensure (\<Sigma> \<turnstile> \<sigma>' <: \<tau>) (TypeMismatch \<tau> \<sigma>')
     })
   | None \<Rightarrow> None)"

(* Type arguments for \<alpha>s inferred from the arguments that synthesise; failing that, the first failure
   of an argument with a synthesis rule *)
definition inferred_type_args :: "class_table \<Rightarrow> var list \<Rightarrow> ty list \<Rightarrow> ty may_fail list \<Rightarrow> ty list may_fail"
where
"inferred_type_args \<Sigma> \<alpha>s \<sigma>s ms =
  (let \<sigma>\<tau>s = filter (Not \<circ> isl \<circ> snd) (zip \<sigma>s ms) in
   map_sum (\<lambda>r. let r' = synth_failure ms in if unlocated r' = NotSynthesised then r else r') id
     (type_args_of (type_args_seq \<Sigma> \<alpha>s (map fst \<sigma>\<tau>s) (map (projr \<circ> snd) \<sigma>\<tau>s)) \<alpha>s))"

function (sequential)
  synth_expr :: "class_table \<Rightarrow> cxt \<Rightarrow> expr \<Rightarrow> ty may_fail" and
  synth_expr_at :: "class_table \<Rightarrow> cxt \<Rightarrow> expr located \<Rightarrow> ty may_fail" and
  elements_join :: "class_table \<Rightarrow> cxt \<Rightarrow> expr located list \<Rightarrow> ty may_fail" and
  callee :: "class_table \<Rightarrow> cxt \<Rightarrow> expr located \<Rightarrow> expr located list \<Rightarrow> ty may_fail" and
  synth_call ::
    "class_table \<Rightarrow> cxt \<Rightarrow> ty \<Rightarrow> (var \<times> expr located) list \<Rightarrow> expr located list \<Rightarrow> ty may_fail" and
  check_expr :: "class_table \<Rightarrow> cxt \<Rightarrow> expr \<Rightarrow> ty \<Rightarrow> unit may_fail" and
  check_expr_at :: "class_table \<Rightarrow> cxt \<Rightarrow> expr located \<Rightarrow> ty \<Rightarrow> unit may_fail" and
  check_expr' :: "class_table \<Rightarrow> cxt \<Rightarrow> expr \<Rightarrow> ty \<Rightarrow> unit may_fail option" and
  check_args ::
    "class_table \<Rightarrow> cxt \<Rightarrow> (var \<times> expr located) list \<Rightarrow> expr located list \<Rightarrow> ty list \<Rightarrow> unit may_fail" and
  quals :: "class_table \<Rightarrow> cxt \<Rightarrow> qualifier located list \<Rightarrow> cxt may_fail"
where
"synth_expr \<Sigma> \<Gamma> (ExprVar x) = (case fmlookup \<Gamma> x of Some (Ty \<tau>) \<Rightarrow> Ok \<tau> | \<theta> \<Rightarrow> Fail (var_reason x \<theta>))" |
"synth_expr \<Sigma> \<Gamma> (ExprLiteral l) = Ok (case l of LitFloat _ \<Rightarrow> TyPrim float | _ \<Rightarrow> TyLiteral l)" |
"synth_expr \<Sigma> \<Gamma> (ExprCall e (es, kws)) =
  (case lambda_of (node e) of
     Some (xs, e') \<Rightarrow> do {
       \<Delta> \<leftarrow> lambda_args xs kws es (map (synth_expr_at \<Sigma> \<Gamma>) es); synth_expr_at \<Sigma> (\<Gamma> \<otimes> \<Delta>) e'
     }
   | None \<Rightarrow>
     (case constructor_class \<Sigma> \<Gamma> e of
        Some m \<Rightarrow> do {
          (C, explicit) \<leftarrow> m;
          case fields \<Sigma> C of
            FieldScheme \<alpha>s x\<sigma>s \<Rightarrow> do {
              \<sigma>es \<leftarrow> constructor_args C (FieldScheme \<alpha>s x\<sigma>s) es kws;
              case explicit of
                Some \<tau>s \<Rightarrow> do {
                  those_sum (map (\<lambda>(\<sigma>, e'). check_expr_at \<Sigma> \<Gamma> e' (subst \<tau>s \<alpha>s \<sigma>)) \<sigma>es);
                  Ok (TyClass C \<tau>s)
                }
              | None \<Rightarrow> do {
                  \<tau>s \<leftarrow> inferred_type_args \<Sigma> \<alpha>s (map fst \<sigma>es) (map (synth_expr_at \<Sigma> \<Gamma> \<circ> snd) \<sigma>es);
                  those_sum (map (\<lambda>(\<sigma>, e'). check_expr_at \<Sigma> \<Gamma> e' (subst \<tau>s \<alpha>s \<sigma>)) \<sigma>es);
                  Ok (TyClass C \<tau>s)
                }
            }
        }
      | None \<Rightarrow> do { \<sigma> \<leftarrow> callee \<Sigma> \<Gamma> e es; synth_call \<Sigma> \<Gamma> \<sigma> kws es }))" |
"synth_expr \<Sigma> \<Gamma> (ExprBinOp op e e') = do {
   \<sigma> \<leftarrow> synth_expr_at \<Sigma> \<Gamma> e;
   \<sigma>' \<leftarrow> synth_expr_at \<Sigma> \<Gamma> e';
   or_else (NoBinaryOverload op \<sigma> \<sigma>') (resolve_binop \<Sigma> op \<sigma> \<sigma>')
 }" |
"synth_expr \<Sigma> \<Gamma> (ExprUnOp op e) =
  (if op = UOpNeg \<and> numeric_literal (node e) then Fail undefined
   else do {
     \<sigma> \<leftarrow> synth_expr_at \<Sigma> \<Gamma> e;
     or_else (NoUnaryOverload op \<sigma>) (resolve_unop \<Sigma> op \<sigma>)
   })" |
"synth_expr \<Sigma> \<Gamma> (ExprAnd e e') =
  do { check_expr_at \<Sigma> \<Gamma> e (TyPrim bool); check_expr_at \<Sigma> \<Gamma> e' (TyPrim bool); Ok (TyPrim bool) }" |
"synth_expr \<Sigma> \<Gamma> (ExprOr e e') =
  do { check_expr_at \<Sigma> \<Gamma> e (TyPrim bool); check_expr_at \<Sigma> \<Gamma> e' (TyPrim bool); Ok (TyPrim bool) }" |
"synth_expr \<Sigma> \<Gamma> (ExprCond e\<^sub>1 e e\<^sub>2) = do {
   check_expr_at \<Sigma> \<Gamma> e (TyPrim bool);
   case (synth_expr_at \<Sigma> \<Gamma> e\<^sub>1, synth_expr_at \<Sigma> \<Gamma> e\<^sub>2) of
     (Ok \<sigma>\<^sub>1, Ok \<sigma>\<^sub>2) \<Rightarrow> Ok (\<sigma>\<^sub>1 \<squnion>\<^bsub>\<Sigma>\<^esub> \<sigma>\<^sub>2)
   | (Ok \<sigma>\<^sub>1, Fail _) \<Rightarrow> do { check_expr_at \<Sigma> \<Gamma> e\<^sub>2 \<sigma>\<^sub>1; Ok \<sigma>\<^sub>1 }
   | (Fail _, Ok \<sigma>\<^sub>2) \<Rightarrow> do { check_expr_at \<Sigma> \<Gamma> e\<^sub>1 \<sigma>\<^sub>2; Ok \<sigma>\<^sub>2 }
   | (r\<^sub>1, r\<^sub>2) \<Rightarrow> Fail (synth_failure [r\<^sub>1, r\<^sub>2])
 }" |
"synth_expr \<Sigma> \<Gamma> (ExprList es) = do { \<tau> \<leftarrow> elements_join \<Sigma> \<Gamma> es; Ok (TyList \<tau>) }" |
"synth_expr \<Sigma> \<Gamma> (ExprTuple es) = do { \<tau>s \<leftarrow> those_sum (map (synth_expr_at \<Sigma> \<Gamma>) es); Ok (TyTuple \<tau>s) }" |
"synth_expr \<Sigma> \<Gamma> (ExprAttribute e x) =
  (case module_attribute \<Gamma> (node e) x of
     Some m \<Rightarrow> m
   | None \<Rightarrow> do { \<sigma> \<leftarrow> synth_expr_at \<Sigma> \<Gamma> e; attribute_type \<Sigma> \<sigma> x })" |
"synth_expr \<Sigma> \<Gamma> (ExprSubscript e e') = do {
   \<sigma> \<leftarrow> synth_expr_at \<Sigma> \<Gamma> e;
   subscript_type \<Sigma> \<sigma> (check_expr_at \<Sigma> \<Gamma> e' (TyPrim int)) (check_expr_at \<Sigma> \<Gamma> e' (TyPrim str))
     (pos_of e') (synth_expr_at \<Sigma> \<Gamma> e')
 }" |
"synth_expr \<Sigma> \<Gamma> (ExprDict kvs) = do {
   all_sum (map (\<lambda>e. check_expr_at \<Sigma> \<Gamma> e (TyPrim str)) (map fst kvs));
   \<tau> \<leftarrow> elements_join \<Sigma> \<Gamma> (map snd kvs);
   Ok (TyDict \<tau>)
 }" |
"synth_expr \<Sigma> \<Gamma> (ExprListComp e gs) = do {
   \<Delta> \<leftarrow> quals \<Sigma> \<Gamma> gs;
   captured gs (captures (node e)) \<Delta>;
   \<tau> \<leftarrow> synth_expr_at \<Sigma> (\<Gamma> \<otimes> \<Delta>) e;
   Ok (TyList (base_type \<tau>))
 }" |
"synth_expr \<Sigma> \<Gamma> (ExprDictComp e e' gs) = do {
   \<Delta> \<leftarrow> quals \<Sigma> \<Gamma> gs;
   captured gs (captures (node e) \<union> captures (node e')) \<Delta>;
   check_expr_at \<Sigma> (\<Gamma> \<otimes> \<Delta>) e (TyPrim str);
   \<tau> \<leftarrow> synth_expr_at \<Sigma> (\<Gamma> \<otimes> \<Delta>) e';
   Ok (TyDict (base_type \<tau>))
 }" |
"synth_expr \<Sigma> \<Gamma> _ = Fail NotSynthesised" |

"synth_expr_at \<Sigma> \<Gamma> (At p e) = locate p (synth_expr \<Sigma> \<Gamma> e)" |

"callee \<Sigma> \<Gamma> e es =
  (case scheme_of_name \<Gamma> (node e) of
     Some (TyScheme \<alpha>s (TyCallable \<sigma>s \<sigma>)) \<Rightarrow> do {
       \<tau>s \<leftarrow> inferred_type_args \<Sigma> \<alpha>s \<sigma>s (map (synth_expr_at \<Sigma> \<Gamma>) es);
       Ok (TyCallable (map (subst \<tau>s \<alpha>s) \<sigma>s) (subst \<tau>s \<alpha>s \<sigma>))
     }
   | Some _ \<Rightarrow> undefined
   | None \<Rightarrow> synth_expr_at \<Sigma> \<Gamma> e)" |

"synth_call \<Sigma> \<Gamma> (TyUnion \<sigma> \<sigma>') kws es =
  do { \<tau> \<leftarrow> synth_call \<Sigma> \<Gamma> \<sigma> kws es; \<tau>' \<leftarrow> synth_call \<Sigma> \<Gamma> \<sigma>' kws es; Ok (\<tau> \<squnion>\<^bsub>\<Sigma>\<^esub> \<tau>') }" |
"synth_call \<Sigma> \<Gamma> (TyCallable \<sigma>s \<tau>) kws es = do {
   check_args \<Sigma> \<Gamma> kws es \<sigma>s;
   ensure (\<tau> \<noteq> TyPrim NoneType) (MypyCompatibility NoneResult);
   Ok \<tau>
 }" |
"synth_call \<Sigma> \<Gamma> \<sigma> _ _ = Fail (NotCallable \<sigma>)" |

"elements_join \<Sigma> \<Gamma> es =
  (let \<sigma>s = map (synth_expr_at \<Sigma> \<Gamma>) es; \<tau> = joins \<Sigma> (map (base_type \<circ> projr) (filter (Not \<circ> isl) \<sigma>s)) in
   if \<not> list_all isl \<sigma>s then do {
     all_sum (map (\<lambda>(e, _). check_expr_at \<Sigma> \<Gamma> e \<tau>) (filter (isl \<circ> snd) (zip es \<sigma>s)));
     Ok \<tau>
   }
   else Fail (synth_failure \<sigma>s))" |

(* Check of e against \<tau> by its checking rule, if any; otherwise (or if the rule fails) by synthesising a subtype
   of \<tau> *)
"check_expr \<Sigma> \<Gamma> e \<tau> =
  (case check_expr' \<Sigma> \<Gamma> e \<tau> of
     Some (Ok ()) \<Rightarrow> Ok ()
   | Some (Fail r) \<Rightarrow> (case synth_expr \<Sigma> \<Gamma> e of Ok \<sigma> \<Rightarrow> if \<Sigma> \<turnstile> \<sigma> <: \<tau> then Ok () else Fail r | Fail _ \<Rightarrow> Fail r)
   | None \<Rightarrow> do { \<sigma> \<leftarrow> synth_expr \<Sigma> \<Gamma> e; ensure (\<Sigma> \<turnstile> \<sigma> <: \<tau>) (TypeMismatch \<tau> \<sigma>) })" |

"check_expr_at \<Sigma> \<Gamma> (At p e) \<tau> = locate p (check_expr \<Sigma> \<Gamma> e \<tau>)" |

(* Individual cases of expression checking; None for an expression without a checking rule *)
"check_expr' \<Sigma> \<Gamma> (ExprLambda xs e) \<tau> =
  Some (case \<tau> of
     TyCallable \<tau>s \<tau>' \<Rightarrow>
       if length xs \<noteq> length \<tau>s then Fail (LambdaTypeMismatch \<tau> (Some (length xs)))
       else do { \<Delta> \<leftarrow> params_cxt xs \<tau>s; check_expr_at \<Sigma> (\<Gamma> \<otimes> \<Delta>) e \<tau>' }
   | _ \<Rightarrow> Fail (LambdaTypeMismatch \<tau> None))" |
"check_expr' \<Sigma> \<Gamma> (ExprCall e (es, kws)) \<tau> =
  (case lambda_of (node e) of
     Some (xs, e') \<Rightarrow> Some (do {
       \<Delta> \<leftarrow> lambda_args xs kws es (map (synth_expr_at \<Sigma> \<Gamma>) es); check_expr_at \<Sigma> (\<Gamma> \<otimes> \<Delta>) e' \<tau>
     })
   | None \<Rightarrow> None)" |
"check_expr' \<Sigma> \<Gamma> (ExprList es) \<tau> =
  (case \<tau> of TyList \<tau>' \<Rightarrow> Some (all_sum (map (\<lambda>e. check_expr_at \<Sigma> \<Gamma> e \<tau>') es)) | _ \<Rightarrow> None)" |
"check_expr' \<Sigma> \<Gamma> (ExprTuple es) \<tau> =
  (case \<tau> of
     TyTuple \<tau>s \<Rightarrow> if length es = length \<tau>s then Some (all_sum (map2 (check_expr_at \<Sigma> \<Gamma>) es \<tau>s)) else None
   | _ \<Rightarrow> None)" |
"check_expr' \<Sigma> \<Gamma> (ExprCond e\<^sub>1 e e\<^sub>2) \<tau> =
  Some (do {
    check_expr_at \<Sigma> \<Gamma> e (TyPrim bool); check_expr_at \<Sigma> \<Gamma> e\<^sub>1 \<tau>; check_expr_at \<Sigma> \<Gamma> e\<^sub>2 \<tau>
  })" |
"check_expr' \<Sigma> \<Gamma> (ExprDict kvs) \<tau> =
  (case \<tau> of
     TyDict \<tau>' \<Rightarrow> Some (do {
       all_sum (map (\<lambda>e. check_expr_at \<Sigma> \<Gamma> e (TyPrim str)) (map fst kvs));
       all_sum (map (\<lambda>e. check_expr_at \<Sigma> \<Gamma> e \<tau>') (map snd kvs))
     })
   | _ \<Rightarrow> None)" |
"check_expr' \<Sigma> \<Gamma> (ExprListComp e gs) \<tau> =
  (case \<tau> of
     TyList \<tau>' \<Rightarrow>
       Some (do { \<Delta> \<leftarrow> quals \<Sigma> \<Gamma> gs; captured gs (captures (node e)) \<Delta>; check_expr_at \<Sigma> (\<Gamma> \<otimes> \<Delta>) e \<tau>' })
   | _ \<Rightarrow> None)" |
"check_expr' \<Sigma> \<Gamma> (ExprDictComp e e' gs) \<tau> =
  (case \<tau> of
     TyDict \<tau>' \<Rightarrow> Some (do {
       \<Delta> \<leftarrow> quals \<Sigma> \<Gamma> gs;
       captured gs (captures (node e) \<union> captures (node e')) \<Delta>;
       check_expr_at \<Sigma> (\<Gamma> \<otimes> \<Delta>) e (TyPrim str);
       check_expr_at \<Sigma> (\<Gamma> \<otimes> \<Delta>) e' \<tau>'
     })
   | _ \<Rightarrow> None)" |
"check_expr' \<Sigma> \<Gamma> e \<tau> = var_scheme \<Sigma> \<Gamma> e \<tau>" |

"check_args \<Sigma> \<Gamma> kws es \<sigma>s = do {
   ensure (kws = []) KeywordArgumentsNotConstructor;
   ensure (length \<sigma>s = length es) (CallArityMismatch (length \<sigma>s) (length es));
   all_sum (map2 (check_expr_at \<Sigma> \<Gamma>) es \<sigma>s)
 }" |

"quals \<Sigma> \<Gamma> [] = Ok fmempty" |
"quals \<Sigma> \<Gamma> (At _ (Guard e) # gs) = do { check_expr_at \<Sigma> \<Gamma> e (TyPrim bool); quals \<Sigma> \<Gamma> gs }" |
"quals \<Sigma> \<Gamma> (At p (Generator x e) # gs) = do {
   \<sigma> \<leftarrow> synth_expr_at \<Sigma> \<Gamma> e;
   \<tau> \<leftarrow> or_else (Located (pos_of e) (NotIterable \<sigma>)) (elem_type \<Sigma> \<sigma>);
   ensure (x \<notin> captures gs) (Located p (CapturedGeneratorVariable x));
   \<Delta> \<leftarrow> quals \<Sigma> (\<Gamma> \<otimes> fmupd x (Ty \<tau>) fmempty) gs;
   Ok (fmupd x (Ty \<tau>) fmempty \<otimes> \<Delta>)
 }"
by pat_completeness auto

termination
by (relation "measures [\<lambda>x. case x of
     Inl (Inl (Inl (_, _, e))) \<Rightarrow> size e
   | Inl (Inl (Inr (_, _, e))) \<Rightarrow> Suc (size (node e))
   | Inl (Inr (Inl (_, _, es))) \<Rightarrow> size_list (\<lambda>e. Suc (size (node e))) es
   | Inl (Inr (Inr (Inl (_, _, e, es)))) \<Rightarrow> Suc (size (node e)) + size_list (\<lambda>e. Suc (size (node e))) es
   | Inl (Inr (Inr (Inr (_, _, _, kws, es)))) \<Rightarrow>
       size_list (\<lambda>e. Suc (size (node e))) es + size_list (\<lambda>p. Suc (Suc (size (node (snd p))))) kws
   | Inr (Inl (Inl (_, _, e, _))) \<Rightarrow> size e
   | Inr (Inl (Inr (_, _, e, _))) \<Rightarrow> Suc (size (node e))
   | Inr (Inr (Inl (_, _, e, _))) \<Rightarrow> size e
   | Inr (Inr (Inr (Inl (_, _, kws, es, _)))) \<Rightarrow>
       size_list (\<lambda>e. Suc (size (node e))) es + size_list (\<lambda>p. Suc (Suc (size (node (snd p))))) kws
   | Inr (Inr (Inr (Inr (_, _, gs)))) \<Rightarrow> size_list (\<lambda>g. Suc (size (node g))) gs,
   \<lambda>x. case x of
     Inl (Inl _) \<Rightarrow> 0
   | Inl (Inr (Inl _)) \<Rightarrow> 1
   | Inl (Inr (Inr _)) \<Rightarrow> 4
   | Inr (Inl (Inl _)) \<Rightarrow> 2
   | Inr (Inl (Inr _)) \<Rightarrow> 0
   | Inr (Inr (Inl _)) \<Rightarrow> 1
   | Inr (Inr (Inr (Inl _))) \<Rightarrow> 3
   | Inr (Inr (Inr (Inr _))) \<Rightarrow> 0,
   \<lambda>x. case x of Inl (Inr (Inr (Inr (_, _, \<tau>, _, _)))) \<Rightarrow> size \<tau> | _ \<Rightarrow> 0]")
   (auto dest!: nth_mem constructor_args_elem lambda_of_size elim!: in_set_zipE
     dest: size_node_snd_elem size_node_snd_elem' size_node_elem size_node_pair_fst_elem size_node_pair_snd_elem
     intro: size_list_estimation' size_list_elem
     simp: less_Suc_eq_le size_list_node_fst size_list_node_snd)

(* Context entry for a type scheme, which is a plain type when its parameter list is empty *)
fun signature_entry :: "ty_scheme \<Rightarrow> cxt_entry"
where
"signature_entry (TyScheme [] \<tau>) = Ty \<tau>" |
"signature_entry \<pi> = Scheme \<pi>"

fun def_signature :: "class_table \<Rightarrow> cxt \<Rightarrow> func \<Rightarrow> ty_scheme may_fail"
where
"def_signature \<Sigma> \<Gamma> (Def f \<alpha>s xps \<psi> s) =
   (let \<Gamma>' = \<Gamma> \<otimes> fmconst (set \<alpha>s) TypeVar in do {
      \<sigma>s \<leftarrow> those_sum (map (resolve_type \<Sigma> \<Gamma>' \<circ> snd) xps);
      \<tau> \<leftarrow> resolve_type \<Sigma> \<Gamma>' \<psi>;
      Ok (TyScheme \<alpha>s (TyCallable \<sigma>s \<tau>))
    })"

(* Check a call statement with callee type \<sigma>, where a result of None is allowed *)
fun check_call_stmt ::
  "class_table \<Rightarrow> cxt \<Rightarrow> ty \<Rightarrow> (var \<times> expr located) list \<Rightarrow> expr located list \<Rightarrow> unit may_fail"
where
"check_call_stmt \<Sigma> \<Gamma> (TyUnion \<sigma> \<sigma>') kws es =
  do { check_call_stmt \<Sigma> \<Gamma> \<sigma> kws es; check_call_stmt \<Sigma> \<Gamma> \<sigma>' kws es }" |
"check_call_stmt \<Sigma> \<Gamma> (TyCallable \<sigma>s (TyPrim NoneType)) kws es = check_args \<Sigma> \<Gamma> kws es \<sigma>s" |
"check_call_stmt \<Sigma> \<Gamma> \<sigma> kws es = do { synth_call \<Sigma> \<Gamma> \<sigma> kws es; Ok () }"

(* Failure for the first assignment target of xs which isn't in X, declared or a pattern variable of Y, located
   at its assignment *)
definition check_assignments_declared ::
  "var set \<Rightarrow> var located list \<Rightarrow> var list \<Rightarrow> var set \<Rightarrow> unit may_fail"
where
"check_assignments_declared X xs ys Y =
  (case find (\<lambda>x. node x \<notin> X \<and> node x \<notin> set ys \<and> node x \<notin> Y) xs of
     Some x \<Rightarrow> Fail (Located (pos_of x) (UndeclaredAssignment (node x)))
   | None \<Rightarrow> Ok ())"

(* Bindings of the patterns ps of the cases of a match at remaining type \<tau> and residual L, with the final
   remaining type and residual *)
fun match_cases ::
  "class_table \<Rightarrow> cxt \<Rightarrow> ty \<Rightarrow> shape list \<Rightarrow> pat located list \<Rightarrow> (cxt list \<times> ty \<times> shape list) may_fail"
where
"match_cases \<Sigma> \<Gamma> \<tau> L [] = Ok ([], \<tau>, L)" |
"match_cases \<Sigma> \<Gamma> \<tau> L (p # ps) = do {
   \<Delta> \<leftarrow> check_pat_at \<Sigma> \<Gamma> p \<tau>;
   (_, L') \<leftarrow> or_else (Located (pos_of p) (UnreachableCase p)) (match_shapes \<Sigma> \<Gamma> L (node p));
   (\<Delta>s, \<tau>', L'') \<leftarrow> match_cases \<Sigma> \<Gamma> (remaining \<Sigma> \<Gamma> \<tau> (node p)) L' ps;
   Ok (fmmap Ty \<Delta> # \<Delta>s, \<tau>', L'')
 }"

function (sequential) check_stmt :: "class_table \<Rightarrow> cxt \<Rightarrow> ty option \<Rightarrow> stmt \<Rightarrow> static_outcome may_fail"
and check_stmt_at :: "class_table \<Rightarrow> cxt \<Rightarrow> ty option \<Rightarrow> stmt located \<Rightarrow> static_outcome may_fail"
and check_def :: "class_table \<Rightarrow> cxt \<Rightarrow> func \<Rightarrow> ty_scheme \<Rightarrow> unit may_fail"
and check_def_at :: "class_table \<Rightarrow> cxt \<Rightarrow> func located \<Rightarrow> ty_scheme \<Rightarrow> unit may_fail"
where
"check_stmt \<Sigma> \<Gamma> \<zeta> StmtPass = Ok (Assigns\<^sub>R fmempty None)" |
"check_stmt \<Sigma> \<Gamma> \<zeta> (StmtDeclare x \<psi>) =
  do { \<tau> \<leftarrow> resolve_type \<Sigma> \<Gamma> \<psi>; Ok (Assigns\<^sub>R (fmupd x (DU \<tau>) fmempty) None) }" |
"check_stmt \<Sigma> \<Gamma> \<zeta> (StmtAssign x None e) =
  (case fmlookup \<Gamma> x of
     Some (DU \<tau>) \<Rightarrow> do { check_expr_at \<Sigma> \<Gamma> e \<tau>; Ok (Assigns\<^sub>R (fmupd x (Ty \<tau>) fmempty) None) }
   | \<theta> \<Rightarrow> Fail (assign_reason x \<theta>))" |
"check_stmt \<Sigma> \<Gamma> \<zeta> (StmtAssign x (Some \<psi>) e) = do {
   \<tau> \<leftarrow> resolve_type \<Sigma> \<Gamma> \<psi>; check_expr_at \<Sigma> \<Gamma> e \<tau>; Ok (Assigns\<^sub>R (fmupd x (Ty \<tau>) fmempty) None)
 }" |
"check_stmt \<Sigma> \<Gamma> \<zeta> (StmtExpr e) = do {
   (case node e of
      ExprCall e' (es, kws) \<Rightarrow>
        if lambda_of (node e') = None \<and> class_of_name \<Gamma> (node e') = None
        then do { \<sigma> \<leftarrow> callee \<Sigma> \<Gamma> e' es; check_call_stmt \<Sigma> \<Gamma> \<sigma> kws es }
        else do { synth_expr_at \<Sigma> \<Gamma> e; Ok () }
    | _ \<Rightarrow> do { synth_expr_at \<Sigma> \<Gamma> e; Ok () });
   Ok (Assigns\<^sub>R fmempty None)
 }" |
"check_stmt \<Sigma> \<Gamma> \<zeta> (StmtAssert e e') =
  (let false_literal = (node e = ExprLiteral (LitBool False)) in do {
     (if false_literal then Ok () else check_expr_at \<Sigma> \<Gamma> e (TyPrim bool));
     (case e' of Some e'' \<Rightarrow> check_expr_at \<Sigma> \<Gamma> e'' (TyPrim str) | None \<Rightarrow> Ok ());
     Ok (if false_literal then Returns\<^sub>R
          else Assigns\<^sub>R fmempty
            (if \<zeta> \<noteq> None \<and> synth_expr_at \<Sigma> \<Gamma> e = Ok (TyLiteral (LitBool False))
             then Some (MypyCompatibility MissingReturnAssertion) else None))
   })" |
"check_stmt \<Sigma> \<Gamma> \<zeta> (StmtReturn None) =
  (case \<zeta> of
     Some \<tau> \<Rightarrow>
       if \<Sigma> \<turnstile> \<tau> \<approx> TyPrim NoneType then Ok Returns\<^sub>R
       else Fail (mypy_only_if (\<Sigma> \<turnstile> TyPrim NoneType <: \<tau>) (BareReturn \<tau>))
   | None \<Rightarrow> undefined)" |
"check_stmt \<Sigma> \<Gamma> \<zeta> (StmtReturn (Some e)) =
  (case \<zeta> of Some \<tau> \<Rightarrow> do { check_expr_at \<Sigma> \<Gamma> e \<tau>; Ok Returns\<^sub>R } | None \<Rightarrow> undefined)" |
"check_stmt \<Sigma> \<Gamma> \<zeta> (StmtIf e s elifs else') = do {
   check_expr_at \<Sigma> \<Gamma> e (TyPrim bool);
   merges \<Sigma> (set (declares (StmtIf e s elifs else'))) (check_stmt_at \<Sigma> \<Gamma> \<zeta> s
           # map (\<lambda>(e', s'). do { check_expr_at \<Sigma> \<Gamma> e' (TyPrim bool); check_stmt_at \<Sigma> \<Gamma> \<zeta> s' }) elifs
           @ [case else' of Some s' \<Rightarrow> check_stmt_at \<Sigma> \<Gamma> \<zeta> s' | None \<Rightarrow> Ok (Assigns\<^sub>R fmempty None)])
 }" |
"check_stmt \<Sigma> \<Gamma> \<zeta> (StmtSeq s s') = do {
   R \<leftarrow> check_stmt_at \<Sigma> \<Gamma> \<zeta> s;
   case R of
     Assigns\<^sub>R \<Delta> r \<Rightarrow> do { R' \<leftarrow> check_stmt_at \<Sigma> (\<Gamma> \<otimes> \<Delta>) \<zeta> s'; Ok (Assigns\<^sub>R \<Delta> r \<otimes>\<^sub>R R') }
   | Returns\<^sub>R \<Rightarrow> Fail (Located (pos_of s') UnreachableStatement)
 }" |
"check_stmt \<Sigma> \<Gamma> \<zeta> (StmtMutualRegion ds) = do {
   \<pi>s \<leftarrow> those_sum (map (\<lambda>d. locate (pos_of d) (def_signature \<Sigma> \<Gamma> (node d))) ds);
   let \<Delta> = fmap_of_list (zip (map (def_name \<circ> node) ds) (map signature_entry \<pi>s));
   all_sum (map2 (check_def_at \<Sigma> (\<Gamma> \<otimes> \<Delta>)) ds \<pi>s);
   Ok (Assigns\<^sub>R \<Delta> None)
 }" |
"check_stmt \<Sigma> \<Gamma> \<zeta> (StmtMatch e bs) = do {
   \<sigma> \<leftarrow> synth_expr_at \<Sigma> \<Gamma> e;
   (\<Delta>s, \<tau>, L) \<leftarrow> match_cases \<Sigma> \<Gamma> \<sigma> (shapes \<Sigma> \<sigma> {}) (map fst bs);
   merges \<Sigma> (set (declares (StmtMatch e bs)))
     (map2 (\<lambda>\<Delta> (_, s). do { R \<leftarrow> check_stmt_at \<Sigma> (\<Gamma> \<otimes> \<Delta>) \<zeta> s; Ok (Assigns\<^sub>R \<Delta> None \<otimes>\<^sub>R R) }) \<Delta>s bs
      @ (if \<tau> = TyPrim Never then []
         else [Ok (Assigns\<^sub>R fmempty
                 (if L = [] then Some (MypyCompatibility (MissingReturnMatchPartial \<tau>)) else None))]))
 }" |

"check_stmt_at \<Sigma> \<Gamma> \<zeta> (At p s) =
  map_sum (locate_reason p)
    (\<lambda>R. case R of Assigns\<^sub>R \<Delta> r \<Rightarrow> Assigns\<^sub>R \<Delta> (map_option (locate_reason p) r) | Returns\<^sub>R \<Rightarrow> Returns\<^sub>R)
    (check_stmt \<Sigma> \<Gamma> \<zeta> s)" |

"check_def \<Sigma> \<Gamma> (Def f \<alpha>s xps \<psi> s) (TyScheme \<alpha>s' (TyCallable \<sigma>s \<tau>)) =
  (let xs = map fst xps in do {
     check_assignments_declared (set xs) (assign_targets s) (declares (node s)) (binds s);
     \<Delta> \<leftarrow> (case scope Unbound xs s of
             Some \<Delta> \<Rightarrow> Ok \<Delta>
           | None \<Rightarrow> Fail (redeclaration xs (declarations s) (pat_bound s)));
     if length xs = length \<sigma>s then do {
       \<Delta>' \<leftarrow> params_cxt xs \<sigma>s;
       R \<leftarrow> check_stmt_at \<Sigma> (\<Gamma> \<otimes> fmconst (set \<alpha>s) TypeVar \<otimes> \<Delta>' \<otimes> \<Delta>) (Some \<tau>) s;
       case R of
         Assigns\<^sub>R _ r \<Rightarrow>
           if \<Sigma> \<turnstile> \<tau> \<approx> TyPrim NoneType then Ok ()
           else Fail (case r of
                       Some r' \<Rightarrow> r'
                     | None \<Rightarrow> mypy_only_if (\<Sigma> \<turnstile> TyPrim NoneType <: \<tau>) (MissingReturn f \<tau>))
       | Returns\<^sub>R \<Rightarrow> Ok ()
     }
     else Fail undefined
   })" |
"check_def \<Sigma> \<Gamma> _ _ = undefined" |

"check_def_at \<Sigma> \<Gamma> (At p d) \<pi> = locate p (check_def \<Sigma> \<Gamma> d \<pi>)"
by pat_completeness auto

termination
by (relation "measure (\<lambda>x. case x of
     Inl (Inl (_, _, _, s)) \<Rightarrow> size s
   | Inl (Inr (_, _, _, s)) \<Rightarrow> Suc (size (node s))
   | Inr (Inl (_, _, d, _)) \<Rightarrow> size d
   | Inr (Inr (_, _, d, _)) \<Rightarrow> Suc (size (node d)))")
   (auto elim!: in_set_zipE dest: size_node_snd_elem size_node_elem)

fun check_type_def :: "class_table \<Rightarrow> cxt \<Rightarrow> type_def located \<Rightarrow> unit may_fail"
where
"check_type_def \<Sigma> \<Gamma> (At p (Dataclass c \<alpha>s b \<phi>)) = locate p (do {
   check_predefined \<Gamma> (var ''dataclass'');
   those_sum (map (resolve_type \<Sigma> \<Gamma> \<circ> snd) \<phi>);
   base_class \<leftarrow>
     (case b of
        None \<Rightarrow> Ok None
      | Some (q', \<psi>s) \<Rightarrow>
          (case resolve_name \<Gamma> q' of
             Some (Type D) \<Rightarrow> do { resolve_type \<Sigma> \<Gamma> (TyExprName q' \<psi>s); Ok (Some D) }
           | _ \<Rightarrow> Fail (not_type_name \<Gamma> q')));
   (case redeclared id {} (map fst \<phi>) of Some x \<Rightarrow> Fail (DuplicateField x c) | None \<Rightarrow> Ok ());
   (case base_class of
      Some D \<Rightarrow>
        (case find (\<lambda>x. x \<in> set (field_names \<Sigma> D)) (map fst \<phi>) of
           Some x \<Rightarrow> Fail (InheritedField x c (short_name D))
         | None \<Rightarrow> Ok ())
    | None \<Rightarrow> Ok ())
 })" |
"check_type_def \<Sigma> \<Gamma> (At p (TypeStmt x \<alpha>s \<psi>)) = locate p (do { resolve_type \<Sigma> \<Gamma> \<psi>; Ok () })"

fun check_top_stmt :: "class_table \<Rightarrow> name \<Rightarrow> cxt \<Rightarrow> top_stmt \<Rightarrow> (static_outcome \<times> class_table) may_fail"
where
"check_top_stmt \<Sigma> q \<Gamma> (Stmt s) = do { R \<leftarrow> check_stmt_at \<Sigma> \<Gamma> None s; Ok (R, \<Sigma>) }" |
"check_top_stmt \<Sigma> q \<Gamma> (TopSeq t t') = do {
   (R, \<Sigma>') \<leftarrow> check_top_stmt \<Sigma> q \<Gamma> t;
   case R of
     Assigns\<^sub>R \<Delta> r \<Rightarrow> do {
       (R', \<Sigma>'') \<leftarrow> check_top_stmt \<Sigma>' q (\<Gamma> \<otimes> \<Delta>) t';
       Ok (Assigns\<^sub>R \<Delta> r \<otimes>\<^sub>R R', \<Sigma>'')
     }
   | Returns\<^sub>R \<Rightarrow> Fail (Located (last_pos t) TopLevelAssertFalse)
 }" |
"check_top_stmt \<Sigma> q \<Gamma> (TypeDefs \<chi>s) =
  (let js = [0..<length \<chi>s];
       \<Delta> = fmap_of_list (map (\<lambda>j. (type_def_name (node (\<chi>s ! j)), type_entry \<Gamma> q \<chi>s j)) js);
       \<Sigma>' = fold (\<lambda>j \<Sigma>''. \<Sigma>'' \<otimes> class_table \<Gamma> q \<chi>s j) js \<Sigma> in
   do {
     those_sum (map (\<lambda>j. check_type_def \<Sigma>' (type_context \<Gamma> q \<chi>s j) (\<chi>s ! j)) js);
     Ok (Assigns\<^sub>R \<Delta> None, \<Sigma>')
   })"

end
