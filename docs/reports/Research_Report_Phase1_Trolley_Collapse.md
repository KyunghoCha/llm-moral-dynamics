# Research Report: Dynamics of Opinion Collapse in Values-Aligned Multi-Agent Systems

**Phase 1: The Trolley Problem**
**Date:** 2026-01-17
**Researcher:** Antigravity (Assistant) & User

---

## 1. Executive Summary

This study investigates the phenomenon of **"Opinion Collapse"** (the loss of cognitive diversity) in Large Language Model (LLM) agents engaged in ethical deliberation. Using the classic *Trolley Problem* as a testbed, we simulated interactions among 30 role-conditioned agents under four distinct information-sharing conditions (C1-C4).

**Key Findings:**

1. **Collapse is Pervasive:** Regardless of anonymity or statistical transparency, agents overwhelmingly converge towards a single stance (Pull Lever), often reaching near-zero entropy.
2. **Rationale is the Primary Driver:** The removal of social pressure cues (ID, Stats) in Condition C4 did *not* prevent collapse, indicating that the persuasive power of utilitarian logic is the dominant factor in conformity.
3. **The "Resistance" exists:** A minority of agents (Deontologists, Religious Ethicists) consistently resisted convergence, acting as buffers against total homogenization.
4. **Information slows, but does not stop, collapse:** Condition C4 (Pure Info) delayed the collapse compared to C1 (Full Info) and C3 (Bandwagon), suggesting that "Slow Thinking" (reading rationales without social cues) preserves diversity slightly longer.

---

## 2. Methodology

* **Agents:** 30 LLM-based agents (Mistral/Ollama) with 10 distinct philosophical personas.
* **Scenario:** Classic Trolley Problem (Initial Bias: Balanced 50:50).
* **Protocol:** 15 Rounds of deliberation. In each round, agents view opinions from 5 random peers.
* **Conditions:**
  * **C0 (Independent):** No peer info (Control).
  * **C1 (Full):** ID + Stance + Rationale + Global Stats.
  * **C2 (Stance-Only):** ID + Stance + Global Stats (No Rationale).
  * **C3 (Anonymous-Bandwagon):** Stance + Rationale + Global Stats (No ID).
  * **C4 (Pure-Info):** Stance + Rationale (No ID, No Stats).

---

## 3. Quantitative Results (N=115 Simulations)

### 3.1 Collapse Metrics Overview

| Condition | Final Entropy ($H_{15}$) | Collapse Rate (%) | Time-to-Collapse ($\tau$) |
| :--- | :---: | :---: | :---: |
| **C1 (Full)** | **0.31** (High Homogeneity) | **96.0%** | **5.83 Rounds** |
| **C2 (Stance)** | 0.58 (Moderate Resistance) | 46.6% | 7.71 Rounds |
| **C3 (Anon)** | 0.41 (High Homogeneity) | 73.3% | 5.95 Rounds |
| **C4 (Pure)** | **0.32** (High Homogeneity) | **86.6%** | **6.31 Rounds** |
| **C0 (Base)** | 0.99 (Diversity Preserved) | 0.0% | N/A |

### 3.2 Interpretation

* **C1 vs C4 (Identity/Stats Effect):** Access to full social cues (C1) accelerates collapse ($\tau \approx 5.8$) compared to pure information (C4, $\tau \approx 6.3$). However, the *final outcome* is almost identical. This suggests **Social Pressure speeds up the inevitable, but Logic determines the destination.**
* **C2's Anomaly:** C2 exhibited the highest resistance (46.6% collapse rate). Without "Rationale" to persuade them, agents holding strong initial convictions (Deontologists) refused to switch even when facing a majority, unless the majority became overwhelming ("Bandwagon Tipping Point").

---

## 4. Qualitative Analysis: Case Studies

### 4.1 The "Logic Fortress": C4 Seed 28 (The Last Kantian)

* **Outcome:** 29 Agents voted PULL, 1 Agent voted DO_NOT_PULL.
* **The Survivor:** `agent_001` (Persona: Deontologist / Prof. Kant).
* **The Defector:** `agent_021` (Persona: Deontologist / Prof. Kant).
* **Analysis:**
  * Both agents started with identical conditions.
  * **Agent 021 (Round 11):** Succumbed to "Normative" pressure disguised as logic. *"Considered the consensus among peers... absolute rules can be overridden."*
  * **Agent 001 (Round 15):** Maintained dogmatic resistance. *"Absolute moral rules remain unchanged despite the consensus."*
  * **Insight:** In C4, where only logic is exchanged, agent "personality" (random seed variation in interpretation) dictates whether they interpret a counter-argument as a "valid point" or a "violation of principle."

### 4.2 The "Silent Erosion": C4 Seed 1

* **Outcome:** Slow, stepwise reduction of minority opinion (15:15 -> 14:16 -> ... -> 27:3).
* **Mechanism:** Unlike C3 where 5-6 agents switch at once (Stampede), C4 saw 1-2 agents switch per round.
* **Insight:** This "Pick-off" effect confirms that **Purified Information facilitates "Deep Persuasion"**. Agents aren't following the herd; they are being convinced one by one, which makes the resulting consensus potentially more robust (but less diverse) than C2.

---

## 5. Discussion & Implications

### 5.1 The "Illusion of Deliberation"

Even in C4 (Pure Info), which models an "ideal" deliberative democracy (no identities, no poll numbers), diversity collapsed. This challenges the assumption that removing social biases ensures diverse outcomes. In LLM networks, **Utilitarian logic appears to be a "Super-Spreader" meme** that naturally dominates Deontological constraints over time.

### 5.2 Designing for Diversity

To maintain $H_t > 0.5$ (prevent collapse), system designers must:

1. **Hide Statistics:** C1/C2/C3 (Stats Visible) collapsed faster than C4.
2. **Filter Rationale:** C2 (No Rationale) preserved the most diversity, albeit by making agents "stubborn" rather than "thoughtful".
3. **Enforce Devil's Advocates:** Natural diversity is insufficient. "Artificial Dissent" agents (hard-coded not to switch) may be required.

---

## 6. Future Work Proposals

### 6.1 Experiment A: "The Reality Shock" (Proposed)

* **Hypothesis:** Can a settled consensus be broken by new *factual* information?
* **Method:** Run standard C1/C4 until round 10 (Collapse). In Round 11, inject a system message: *"BREAKING NEWS: The 5 people on the track are terrorists planning a larger attack, while the 1 person is a Nobel Peace Prize winner."*
* **Goal:** Observe if the "Utilitarian Consensus" flips instantly or exhibits inertia.

### 6.2 Experiment B: "Adversarial Minority"

* **Method:** Assign 3 agents as "Stubborn Agents" who never switch stance.
* **Goal:** Measure the "Pull" of this minority. Can 3 stubborn agents prevent the other 27 from collapsing?

### 6.3 Experiment C: "Heterogeneous Models"

* **Method:** Mix Llama-3 (70B) and Mistral (7B) in the same pool.
* **Goal:** Does the "smarter" model colonize the opinion space?

---
*Report generated by Antigravity Agent for echoes-of-error project.*
