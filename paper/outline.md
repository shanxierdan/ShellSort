# Paper outline

## Title

**New Gap of Shellsort: RL-driven Algorithm discovering beyond n^4/3**

The paper typesets the bound as (N^{4/3}). The comparison is with the
classical line of short, sparse, practical gap sequences. It is not a claim
that (N^{4/3}) was the best bound among every known Shellsort construction.

## Main claim

We discover one exact gap generator that is strong in large finite tests and
can be completed into a provable sparse sequence. The executable sequence is

\[
\{1,3,8,20,47,116,300,585\}
\cup\{\lfloor\alpha R^t\rfloor:t\ge12\},
\]

where

\[
\alpha=\frac{420574650882923}{7668945023518835},\qquad
R=\frac{582942583375009}{250000000000000}.
\]

Its proof-preserving completion has worst-case cost

\[
O\!\left(N^{1.024296451657\ldots}\operatorname{polylog}N\right).
\]

## Abstract

One paragraph, with only the final bound displayed on its own line:

1. the gap between practical and provable Shellsort sequences;
2. the RL-driven executable-program search;
3. the final sequence and broad large-scale result;
4. the zero-density completion;
5. the sub-(N^{4/3}) theorem.

## 1. Introduction

### 1.1 Theory, practice, and the 4/3 barrier

- Shell's original algorithm;
- the generalized Frobenius view of one pass and the two competing pass bounds;
- Papernov--Stasevich and Pratt's (N^{3/2}) balance for almost-geometric gaps;
- Pratt's dense (O(N\log^2N)) sequence;
- Sedgewick's three-generator route to the sparse (O(N^{4/3})) construction;
- why more than three generators create modular, coprimality, and embedding
  obstacles;
- Incerpi--Sedgewick's stronger but more complex interleaved-product families;
- Tokuda and Ciura as strong empirical sequences;
- the gap between finite performance and proof;
- our denominator clearing, compound carries, and zero-density unit companions.

### 1.2 AI algorithm discovery

- AlphaGo as learned guidance inside an exact tree search;
- AlphaFold as structured learning checked by blind external evaluation;
- AlphaTensor, AlphaDev, and FunSearch;
- a plain-language explanation that learning proposes while an independent
  evaluator checks;
- the extra Shellsort problem: the output must be one valid generator for all
  (N), not a fixed program or a finite gap table.

### 1.3 Contributions

1. **A new discovery system.** Valid programs, semantic edits, exact learning
   signals, and repeated discovery across five runs.
2. **A stronger practical sequence.** The full exact sequence and the best
   equal-task average over all tested classical baselines.
3. **A bound below (4/3).** A zero-density completion that leaves all reported
   runs unchanged and gives exponent (1.024296451657\ldots).

## 2. RL-driven generator discovery

Only two subsections.

### 2.1 Search problem and program space

- legal Shellsort gap generators;
- exact comparisons-plus-moves objective;
- five input distributions;
- bounded, valid-by-construction program language;
- eight semantic program edits.

### 2.2 Learning and search

- program and behavior encoders;
- 1,099,660-parameter Transformer and four-part loss;
- exact evaluation, replay, random exploration, Pareto archive, cache, and
  checkpoints;
- five seeds and the full search scale;
- Validation freeze and finite-prefix tuning folded into the same workflow.

## 3. Empirical results

Only two subsections and two tables.

### 3.1 From program search to the final sequence

- 40,647 unique behaviors across five complete runs;
- improvement range, late best rounds, replay size, and archive size;
- repeated discovery of ratios between 2.2490 and 2.3619;
- 311-prefix tuning search and independent Validation;
- exact final prefix, rational tail, and first full terms;
- Table 1 collects the self-supervised search, exploration, generalization,
  and tuning metrics.

### 3.2 Performance on large sorting tasks

- 25 equal-weight tasks, five sizes from (10^7) to (10^8), five input types;
- Table 2 compares our sequence with Shell, Hibbard, Knuth, Pratt, Sedgewick,
  Tokuda, and Ciura; Original V3 is not a final baseline;
- raw geometric-mean comparisons, moves, total operations, and reversed total
  are shown in billions;
- green/down and red/up annotations give the change from each baseline to our
  sequence;
- no task-win counts and no separate per-distribution tables;
- aggregate average is the main result; reversed inputs show performance on a
  hard structured case.

## 4. Theory

The main text contains the complete proof flow:

1. turn a Shellsort pass into a generalized Frobenius problem;
2. clear denominators and control holes with compound coordinates, carries,
   and the unit companion;
3. place only (O(\log N/\log\log N)) companions;
4. balance the pass bounds and obtain exponent
   (1+\kappa/(1+\kappa)=1.024296451657\ldots).

It states and proves the compound-coordinate lemma and the unit-companion
conductor lemma, then handles incomplete top windows and finite-prefix tuning.
The final page proves a global-pass-sum proposition by splitting at
(D=N^{1/(1+\kappa)}), summing four pass classes, and ends with the boxed bound
immediately before the Conclusion.
The technical appendix keeps only the expanded normal-form calculation, uniform constant
checks, augmented-kernel bookkeeping, and other technical details. The main
paper, including the full proof flow and Conclusion, ends within the first 12
presentation pages.

## 5. Conclusion

- one sequence links learning, large-scale execution, and proof;
- the completion changes nothing below (10^{1000});
- open questions: the pure backbone, average-case theory, and hardware timing.
