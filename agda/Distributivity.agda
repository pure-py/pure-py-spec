module Distributivity where

open import Data.Bool using (Bool; true; false; _∧_)
open import Data.Bool.Properties using (∧-idem)
open import Data.Maybe using (Maybe; just; nothing)
open import Relation.Binary.PropositionalEquality using (_≡_; refl; sym; cong)

-- Status of a variable in a context: nothing = absent, just true = ⊤, just false = ⊥
Status : Set
Status = Maybe Bool

-- Sequential composition (override): right-biased
_·_ : Status → Status → Status
a · just b = just b
a · nothing = a

-- Parallel composition (merge): meet when both present, ⊥ when only one present
_⊕_ : Status → Status → Status
nothing ⊕ nothing = nothing
nothing ⊕ just _  = just false
just _  ⊕ nothing = just false
just a  ⊕ just b  = just (a ∧ b)

-- Right distributivity of · over ⊕: (a ⊕ b) · c ≡ (a · c) ⊕ (b · c)
-- Left distributivity doesn't hold; see paper for counterexample.
·-distribᵣ-⊕ : ∀ (a b c : Status) → (a ⊕ b) · c ≡ (a · c) ⊕ (b · c)
·-distribᵣ-⊕ nothing  nothing  nothing  = refl
·-distribᵣ-⊕ nothing  nothing  (just c) = cong just (sym (∧-idem c))
·-distribᵣ-⊕ nothing  (just _) nothing  = refl
·-distribᵣ-⊕ nothing  (just _) (just c) = cong just (sym (∧-idem c))
·-distribᵣ-⊕ (just _) nothing  nothing  = refl
·-distribᵣ-⊕ (just _) nothing  (just c) = cong just (sym (∧-idem c))
·-distribᵣ-⊕ (just _) (just _) nothing  = refl
·-distribᵣ-⊕ (just _) (just _) (just c) = cong just (sym (∧-idem c))
