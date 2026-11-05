(* Syntax nodes with their positions in the source *)
theory Positions
  imports Main
begin

type_synonym pos = "nat \<times> nat"

(* Syntax node with its position in the source, as line and column *)
datatype 'a located = At (pos_of: pos) (node: 'a)

definition no_pos :: pos where "no_pos = (0, 0)"

lemma size_located_node [simp]: "size_located f e = Suc (f (node e))"
  by (cases e) simp

lemma size_located_measure [measure_function]: "is_measure f \<Longrightarrow> is_measure (size_located f)"
  by (rule is_measure_trivial)

(* Termination through lists of located nodes and of pairs with a located node, in the normal form of size *)
lemma size_node_elem: "x \<in> set xs \<Longrightarrow> size (node x) < size_list (\<lambda>x. Suc (size (node x))) xs"
  by (induction xs) auto

lemma size_node_snd_elem:
  "(a, b) \<in> set xs \<Longrightarrow> size (node b) < size_list (\<lambda>x. Suc (Suc (size (node (snd x))))) xs"
  by (induction xs) auto

lemma size_node_snd_elem':
  "b \<in> set (map snd xs) \<Longrightarrow> size (node b) < size_list (\<lambda>x. Suc (Suc (size (node (snd x))))) xs"
  by (auto dest: size_node_snd_elem)

lemma size_node_pair_fst_elem:
  "(a, b) \<in> set xs
   \<Longrightarrow> size (node a) < size_list (\<lambda>x. Suc (Suc (Suc (size (node (fst x)) + size (node (snd x)))))) xs"
  by (induction xs) auto

lemma size_node_pair_snd_elem:
  "(a, b) \<in> set xs
   \<Longrightarrow> size (node b) < size_list (\<lambda>x. Suc (Suc (Suc (size (node (fst x)) + size (node (snd x)))))) xs"
  by (induction xs) auto

lemma size_list_node_fst:
  "size_list ((\<lambda>e. Suc (size (node e))) \<circ> fst) kvs
   \<le> size_list (\<lambda>x. Suc (Suc (Suc (size (node (fst x)) + size (node (snd x)))))) kvs"
  by (rule size_list_pointwise) simp

lemma size_list_node_snd:
  "size_list ((\<lambda>e. Suc (size (node e))) \<circ> snd) kvs
   \<le> size_list (\<lambda>x. Suc (Suc (Suc (size (node (fst x)) + size (node (snd x)))))) kvs"
  by (rule size_list_pointwise) simp

end
