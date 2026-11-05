(* Shared utilities *)
theory Util
  imports "HOL-Library.Finite_Map" "HOL-Library.Monad_Syntax"
begin

notation fmadd (infixl "\<otimes>" 100)

type_synonym 'a nonempty = "'a \<times> 'a list"

fun snoc :: "'a nonempty \<Rightarrow> 'a \<Rightarrow> 'a nonempty"
where
"snoc (y, ys) x = (y, ys @ [x])"

fun unsnoc :: "'a nonempty \<Rightarrow> ('a nonempty \<times> 'a) option"
where
"unsnoc (y, ys) = (if ys = [] then None else Some ((y, butlast ys), last ys))"

lemma unsnoc_snoc [simp]: "unsnoc (snoc q x) = Some (q, x)"
  by (cases q) simp

lemma snoc_unsnoc: "unsnoc q' = Some (q, x) \<Longrightarrow> q' = snoc q x"
  by (cases q') (auto split: if_splits simp: append_butlast_last_id)

lemma snoc_eq_iff:
  "snoc q x = q' \<longleftrightarrow> unsnoc q' = Some (q, x)" "q' = snoc q x \<longleftrightarrow> unsnoc q' = Some (q, x)"
  by (auto dest: snoc_unsnoc)

definition fmconst :: "'a set \<Rightarrow> 'b \<Rightarrow> ('a, 'b) fmap"
where
"fmconst A u = Finite_Set.fold (\<lambda>x. fmupd x u) fmempty A"

lemma comp_fun_idem_fmupd: "comp_fun_idem_on UNIV (\<lambda>x. fmupd x u)"
  by unfold_locales (auto simp: fun_eq_iff intro!: fmap_ext)

lemma fmconst_code [code]: "fmconst (set xs) u = fold (\<lambda>x. fmupd x u) xs fmempty"
  unfolding fmconst_def by (rule comp_fun_idem_on.fold_set_fold[OF comp_fun_idem_fmupd subset_UNIV])

(* Termination through lists of pairs and finite maps *)
lemma size_prod_pair [simp]: "size_prod f g p = f (fst p) + g (snd p) + Suc 0"
  by (cases p) simp

lemma size_list_elem: "x \<in> set xs \<Longrightarrow> f x < size_list f xs"
  by (induction xs) auto

lemma size_list_zip_elem: "(x, y) \<in> set (zip xs ys) \<Longrightarrow> f x + g y < size_list f xs + size_list g ys"
  by (metis add_strict_mono set_zip_leftD set_zip_rightD size_list_elem)

lemma size_list_snd_elem: "(a, b) \<in> set xs \<Longrightarrow> size b < size_list (\<lambda>x. Suc (size (snd x))) xs"
  by (induction xs) auto

lemma size_list_snd_elem': "b \<in> set (map snd xs) \<Longrightarrow> size b < size_list (\<lambda>x. Suc (size (snd x))) xs"
  by (auto dest: size_list_snd_elem)

lemma size_list_fst: "size_list (size \<circ> fst) kvs \<le> size_list (\<lambda>x. Suc (size (fst x) + size (snd x))) kvs"
  by (rule size_list_pointwise) simp

lemma size_list_snd: "size_list (size \<circ> snd) kvs \<le> size_list (\<lambda>x. Suc (size (fst x) + size (snd x))) kvs"
  by (rule size_list_pointwise) simp

lemma fmmap_keys_cong [fundef_cong]:
  assumes "m = m'" and "\<And>x v. fmlookup m' x = Some v \<Longrightarrow> f x v = g x v"
  shows "fmmap_keys f m = fmmap_keys g m'"
proof (rule fmap_ext)
  fix x
  show "fmlookup (fmmap_keys f m) x = fmlookup (fmmap_keys g m') x"
    using assms by (cases "fmlookup m' x") simp_all
qed

lemma size_fmap_lookup: "fmlookup m x = Some v \<Longrightarrow> g v < size_fmap f g m"
  using member_le_sum[of "(x, v)" "fset (fset_of_fmap m)" "\<lambda>(a, b). Suc (f a + g b)"]
  by (simp add: fset_of_fmap_iff' case_prod_unfold)

lemma card_fmdom_insert:
  assumes "fmlookup M q = Some m" and "q \<notin> V"
  shows "card (fmdom' M - insert q V) < card (fmdom' M - V)"
proof -
  have "q \<in> fmdom' M - V" using assms by (simp add: fmlookup_dom'_iff)
  moreover have "fmdom' M - insert q V = (fmdom' M - V) - {q}" by auto
  ultimately show ?thesis by (metis card_Diff1_less finite_Diff finite_fmdom')
qed

(* Error monad: failure Fail e or result Ok x *)
abbreviation Fail :: "'e \<Rightarrow> 'e + 'a" where "Fail \<equiv> Inl"
abbreviation Ok :: "'a \<Rightarrow> 'e + 'a" where "Ok \<equiv> Inr"

definition bind_sum :: "'e + 'a \<Rightarrow> ('a \<Rightarrow> 'e + 'b) \<Rightarrow> 'e + 'b"
where
"bind_sum m f = (case m of Fail e \<Rightarrow> Fail e | Ok x \<Rightarrow> f x)"

adhoc_overloading Monad_Syntax.bind \<rightleftharpoons> bind_sum

(* Failure e for None, otherwise the value; e is computed eagerly by generated code *)
definition or_else :: "'e \<Rightarrow> 'a option \<Rightarrow> 'e + 'a"
where
"or_else e m = (case m of Some x \<Rightarrow> Ok x | None \<Rightarrow> Fail e)"

(* First failure in the list, otherwise success *)
fun all_sum :: "('e + unit) list \<Rightarrow> 'e + unit"
where
"all_sum [] = Ok ()" |
"all_sum (m # ms) = do { m; all_sum ms }"

lemma bind_sum_simps [simp]: "bind_sum (Fail e) f = Fail e" "bind_sum (Ok x) f = f x"
  by (simp_all add: bind_sum_def)

lemma bind_sum_cong [fundef_cong]:
  "\<lbrakk> m = m' ; \<And>x. m' = Ok x \<Longrightarrow> f x = f' x \<rbrakk> \<Longrightarrow> bind_sum m f = bind_sum m' f'"
  by (cases m') simp_all

(* Failure e unless b; e is computed eagerly by generated code *)
definition ensure :: "bool \<Rightarrow> 'e \<Rightarrow> 'e + unit"
where
"ensure b e = (if b then Ok () else Fail e)"

(* First failure in the list, otherwise the list of results *)
fun those_sum :: "('e + 'a) list \<Rightarrow> 'e + 'a list"
where
"those_sum [] = Ok []" |
"those_sum (m # ms) = do { x \<leftarrow> m; xs \<leftarrow> those_sum ms; Ok (x # xs) }"

end
