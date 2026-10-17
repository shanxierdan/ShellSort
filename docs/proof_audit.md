# Proof-condition audit

## Status

The appendix proof has been checked lemma by lemma against the exact frozen
constants and the cited semigroup results.  After making previously implicit
hypotheses explicit, no counterexample or missing pass class was found.  The
proved object remains the finite-prefix-preserving completion
\(\mathcal H^\sharp_{\rm tune}\), not the uncompleted geometric backbone.

This is a project-internal proof audit, not a substitute for independent peer
review.

The executable regression suite contains 85 tests, including four exact
proof-completion test groups; all 85 pass.  The paper also compiles to a 23-page
PDF without undefined references or overfull/underfull boxes.

## Conditions now stated explicitly

- \(A>B\ge2\), \(\gcd(A,B)=1\), and the rational \(\alpha\) is exact.
- Window and conductor lemmas are invoked only for a fixed sufficiently large
  \(t\ge t_*\); all excluded indices form a finite early prefix.
- The conductor theorem takes
  \(d\in\{h_t,h_t+1\}\), \(m=m(t)\), and a unit pair at an integer offset
  \(1\le j\le m\).
- The unit pair must occur among larger gaps already executed before the
  current pass.  The strict offset inequality $j<m(t)$ leaves one further
  backbone gap in the window, which certifies $h_{t+j}+1<N$ as well as
  $h_{t+j}<N$.
- The augmented real representation reserves margin
  \(S\ge C_{A,B}m\) in every original and companion coordinate.
- Top gaps with incomplete windows use the independent \(O(N^2/d)\) bound and
  never invoke the conductor theorem.

## Lemma-by-lemma closure

1. **Pass reduction.** The Incerpi--Sedgewick bound applies to the number of
   positive multiples of \(d\) not represented by already executed larger
   gaps.  The direct residue-class insertion bound supplies \(O(N^2/d)\).
2. **Window scales.** From \(A^{m-1}<h_t\le A^m\) and \(R=A/B=A^\kappa\),
   all four scale estimates hold uniformly for both \(h_t\) and \(h_t+1\).
3. **Denominator clearing.** The two-coordinate equations are exact integer
   identities.  For a current companion, all original slopes translate by
   \(-1\); adding a future companion adds exactly \(B^m\) to its error
   coordinate.
4. **Compound threshold.** The weights
   \(B^{m-1},AB^{m-2},\ldots,A^{m-1}\) have the stated normal form and Apéry
   set.  Their Frobenius formula agrees with the compound-sequence theorem.
5. **Complete carry kernel.** Reduction modulo \(A\), followed by induction,
   proves that the adjacent carries generate the full integer kernel, not only
   a sublattice.
6. **Interior representation.** The target lies a positive distance from the
   full augmented slope interval endpoints.  Duplicating one main weight
   increases \(\sum q_i\) by at most a factor of two, so the same uniform
   interior estimate applies.
7. **Integer correction.** Rounding adjacent-carry and unit coordinates leaves
   an integer residual of size \(O_{A,B}(m)\).  The unit direction changes the
   actual value by exactly one.  Margin \(C_{A,B}m\) is sufficient to correct
   the residual while preserving nonnegativity.
8. **Conductor.** The inverse-slope interval has length
   \(\Omega((kB^m/d)R^{-j})\), contains an integer main coordinate above the
   compound Frobenius threshold, and meets the augmented interior condition at
   the stated conductor scale.
9. **Coverage and density.** The next recurrence index is within
   \(\lceil\log(t+2)\rceil<m(t)\).  Dyadic index blocks give
   \(O(T/\log T)\) companions through index \(T\).
10. **Global sum.** Splitting at \(D=N^{1/(1+\kappa)}\) covers small complete
    windows, large complete windows, incomplete top windows, and the finite
    early prefix.  Both non-linear contributions equal \(N^\beta\).

## Exact corrections made during the audit

- \(\kappa=0.024901468995116044855\ldots\).
- Dense-completion exponent
  \(\beta=1.02429645165747606869\ldots\).
- Sparse-alternative exponent
  \(1.04744027301502511325\ldots\).
- The guard is certified by exact cross multiplication:
  \(h_{2723}\le10^{1000}<h_{2724}\).

## Scope that must remain in the paper

- The theorem does not prove the same upper bound for the pure learned tail.
- Constants hidden in \(O_{A,B}(\cdot)\) are finite but extremely large; the
  result is asymptotic rather than a finite-performance explanation.
- Unit companions are part of the mathematical infinite sequence even though
  the guard makes them invisible to every reported experiment.
