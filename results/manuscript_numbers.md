# Regenerated Manuscript Numbers

These values are exported from generated table CSV files. Update the manuscript from this file after rerunning the released seed pool and table-generation workflow.

## Table VII

| Metric | Setting | Algorithm | n | Mean | Std | 95% CI |
| --- | --- | --- | ---: | ---: | ---: | --- |
| Average coverage-quality ratio (Cavg) | Default, N=500, K=5, T=2000s | SCOPE | 50 | 0.933402321948 | 0.00987782269053 | [0.930595075804, 0.936209568092] |
| Average coverage-quality ratio (Cavg) | Default, N=500, K=5, T=2000s | MC3 | 50 | 0.882365736111 | 0.0196755569957 | [0.87677400469, 0.887957467532] |
| Average coverage-quality ratio (Cavg) | Default, N=500, K=5, T=2000s | CAERM | 50 | 0.796416669859 | 0.0461597350707 | [0.783298218318, 0.809535121399] |
| Average coverage-quality ratio (Cavg) | Default, N=500, K=5, T=2000s | Dist-Greedy | 50 | 0.711794575454 | 0.0924990894349 | [0.685506625135, 0.738082525774] |
| Travel-normalized charging efficiency | Dense network, N=600 | SCOPE | 50 | 0.876248095424 | 0.170431181516 | [0.827812089623, 0.924684101226] |
| Travel-normalized charging efficiency | Dense network, N=600 | MC3 | 50 | 0.725409507739 | 0.217565440746 | [0.663578093696, 0.787240921783] |
| Travel-normalized charging efficiency | Dense network, N=600 | CAERM | 50 | 0.557724179488 | 0.0682896689441 | [0.538316470337, 0.57713188864] |
| Travel-normalized charging efficiency | Dense network, N=600 | Dist-Greedy | 50 | 0.545545717115 | 0.0627559040769 | [0.527710686536, 0.563380747694] |
| Dead-node ratio (%) | Default charger setting, K=5 | SCOPE | 50 | 4.42845882947 | 0.742087430926 | [4.21755991537, 4.63935774356] |
| Dead-node ratio (%) | Default charger setting, K=5 | MC3 | 50 | 8.56173934793 | 1.70260554062 | [8.07786420777, 9.04561448809] |
| Dead-node ratio (%) | Default charger setting, K=5 | CAERM | 50 | 16.917501825 | 3.33163980643 | [15.9706602697, 17.8643433804] |
| Dead-node ratio (%) | Default charger setting, K=5 | Dist-Greedy | 50 | 23.0674989369 | 6.41981566147 | [21.2430075155, 24.8919903584] |
| Average charging latency (s) | Default charger setting, K=5 | SCOPE | 50 | 68.8418388546 | 32.4771880765 | [59.61192414, 78.0717535691] |
| Average charging latency (s) | Default charger setting, K=5 | MC3 | 50 | 76.2513146012 | 39.1223273042 | [65.1328722163, 87.3697569862] |
| Average charging latency (s) | Default charger setting, K=5 | CAERM | 50 | 81.1411958365 | 15.4750925954 | [76.7432231882, 85.5391684849] |
| Average charging latency (s) | Default charger setting, K=5 | Dist-Greedy | 50 | 81.7942410843 | 15.0494528018 | [77.5172339267, 86.0712482419] |
| Utility-normalized charging efficiency | Dense network, N=600 | SCOPE | 50 | 7.95805722284 | 0.746477578544 | [7.7459106426, 8.17020380308] |
| Utility-normalized charging efficiency | Dense network, N=600 | MC3 | 50 | 6.23881556748 | 0.617732741139 | [6.06325786514, 6.41437326982] |
| Utility-normalized charging efficiency | Dense network, N=600 | CAERM | 50 | 4.91844472317 | 0.901996553443 | [4.66210013935, 5.17478930699] |
| Utility-normalized charging efficiency | Dense network, N=600 | Dist-Greedy | 50 | 2.79836382686 | 1.12582078808 | [2.47840909945, 3.11831855426] |
| Computation time per decision (ms) | Dense network, N=600 | SCOPE | 50 | 44.738803019 | 2.8498845719 | [43.9288747862, 45.5487312518] |
| Computation time per decision (ms) | Dense network, N=600 | MC3 | 50 | 724.197315823 | 37.503766387 | [713.53886336, 734.855768285] |
| Computation time per decision (ms) | Dense network, N=600 | CAERM | 50 | 971.87471947 | 56.2932659236 | [955.87635033, 987.87308861] |
| Computation time per decision (ms) | Dense network, N=600 | Dist-Greedy | 50 | 8.42500488437 | 1.10037670705 | [8.11228128477, 8.73772848396] |

## Table VIII

Summary of paired statistical tests for representative key comparisons. Differences, confidence intervals, Holm-adjusted p-values, and paired effect sizes are computed from the released paired trial records.

| Comparison | Metric | Baseline | Difference | 95% CI | Test | p_adj | dz | Unit | Interpretation |
| --- | --- | --- | ---: | --- | --- | --- | ---: | --- | --- |
| Fig. 9(b), N=600 | Travel-normalized efficiency | MC3 | 0.150838587685 | [0.0766509246956, 0.225026250675] | Wilcoxon | 0.002 | 0.577829931874 | J/m | Statistically supported efficiency increase over the strongest baseline. |
| Fig. 17(b), S3 | PSM coverage retention | MC3 | 0.76901709256 | [0.682695606399, 0.855338578721] | Wilcoxon | < 0.001 | 2.5318405528 | pp | Statistically supported mean increase under S3. |
| Fig. 17(c), S3 | Dead-node ratio | MC3 | 0.727121951219 | [0.607156904348, 0.847086998091] | Wilcoxon | < 0.001 | 1.7225498361 | pp reduction | Statistically supported mean reduction in node mortality. |
| Fig. 17(d), S3 | Average charging latency | Dist-Greedy | -97.9557618142 | [-114.197958955, -81.7135646733] | Wilcoxon | < 0.001 | -1.71397497563 | s | Raw latency favors the distance-oriented baseline; no latency superiority is claimed for SCOPE. |
| Fig. 18(c), burst window | Peak coverage loss | CAERM | 0.57969556937 | [0.267075237834, 0.892315900906] | Wilcoxon | 0.004 | 0.526989581689 | pp reduction | Statistically supported peak-loss reduction; the absolute effect size remains modest-to-moderate. |
| Fig. 18(d), burst window | Burst-critical outage ratio | MC3 | 0.361941168064 | [0.254702554413, 0.469179781715] | Wilcoxon | < 0.001 | 0.959193132037 | pp reduction | Statistically supported reduction in burst-critical low-energy severity. |
| Fig. 19(a), M3 | PSM coverage retention | MC3 | 0.048077797924 | [-0.0130213027625, 0.109176898611] | Wilcoxon | 0.297 | 0.22362946128 | pp | Comparable robustness; no statistical separation is claimed. |
| Fig. 19(b), M3 | Coverage-critical outage ratio | MC3 | 0.0784933109726 | [0.0316659771699, 0.125320644775] | Wilcoxon | 0.004 | 0.476378864971 | pp reduction | Statistically supported coverage-critical outage reduction; the absolute effect size remains small-to-moderate. |
| Fig. 19(c), M0-M3 | Coverage-critical outage degradation | MC3 | 0.152548125126 | [0.0894472169405, 0.215649033312] | Wilcoxon | < 0.001 | 0.687053461862 | pp reduction | Statistically supported reduction in coverage-critical outage degradation; the absolute effect size remains modest-to-moderate. |
