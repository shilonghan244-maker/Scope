# Seed Files

`monte_carlo_50_trials.csv` contains the 50 paired Monte Carlo trials used by
the paper experiments. Each row separates the random streams used for
deployment, initial energy, demand, mobility, charging efficiency, scenario
variation, and algorithm-local tie breaking.

For a fixed `trial_id`, every compared algorithm must use the same environment
seeds. This is the common-randomness paired Monte Carlo protocol used by the
manuscript.
