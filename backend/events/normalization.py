import math
from typing import Dict, List, Tuple, Any


class NormalizationEngine:
    """
    Empirical Bayes Regularized Z-Score Normalization Engine for Hackathons.
    
    Eliminates Location Bias (mean shifts) and Dispersion Bias (variance shifts) across judges
    while stabilizing small sample sizes (n < 3) and zero-variance scoring via Bayesian shrinkage.
    """
    DEFAULT_GLOBAL_MEAN = 7.0
    DEFAULT_GLOBAL_STD = 1.5
    MIN_PRIOR_WEIGHT = 3.0  # m: shrinkage parameter
    EPSILON = 1e-6

    @classmethod
    def calculate_normalized_scores(
        cls, evaluations: List[Dict[str, Any]]
    ) -> Tuple[Dict[int, float], Dict[int, float], Dict[int, float], Dict[str, Any]]:
        """
        Input: evaluations: list of dicts with keys:
               'id', 'submission_id', 'judge_id', 'total_score'
        Returns:
            - submission_norm_scores: {submission_id: normalized_final_score}
            - submission_raw_scores:  {submission_id: raw_arithmetic_mean}
            - submission_std_err:     {submission_id: standard_error_of_normalized_scores, or None if k == 1}
            - judge_telemetry:        {judge_id: {'raw_mean': float, 'shrunk_mean': float, 'shrunk_std': float, 'count': int}}
        """
        if not evaluations:
            return {}, {}, {}, {}

        # 1. Global Baseline Computation across the entire event
        all_raw_scores = [float(e['total_score']) for e in evaluations]
        n_total = len(all_raw_scores)
        mu_global = sum(all_raw_scores) / n_total

        if n_total > 1:
            var_global = sum((x - mu_global) ** 2 for x in all_raw_scores) / (n_total - 1)
            sigma_global = math.sqrt(var_global) if var_global > cls.EPSILON else cls.DEFAULT_GLOBAL_STD
        else:
            sigma_global = cls.DEFAULT_GLOBAL_STD

        # 2. Per-Judge Partitioning
        judge_scores: Dict[int, List[float]] = {}
        project_raw_scores: Dict[int, List[float]] = {}
        for e in evaluations:
            j_id = e['judge_id']
            sub_id = e['submission_id']
            score = float(e['total_score'])
            judge_scores.setdefault(j_id, []).append(score)
            project_raw_scores.setdefault(sub_id, []).append(score)

        # 3. Empirical Bayes Parameter Estimation per Judge
        judge_params: Dict[int, Tuple[float, float]] = {}
        judge_telemetry: Dict[str, Any] = {}
        m = cls.MIN_PRIOR_WEIGHT

        for j_id, scores in judge_scores.items():
            n_j = len(scores)
            s_bar = sum(scores) / n_j

            if n_j > 1:
                s_var = sum((x - s_bar) ** 2 for x in scores) / (n_j - 1)
            else:
                s_var = 0.0

            # Bayesian Shrunk Mean
            shrunk_mu = (n_j * s_bar + m * mu_global) / (n_j + m)

            # Shrunk Pooled Variance with mean-difference adjustment
            shrunk_var_num = (
                (n_j - 1) * s_var
                + m * (sigma_global ** 2)
                + ((n_j * m) / (n_j + m)) * ((s_bar - mu_global) ** 2)
            )
            shrunk_var_den = n_j + m - 1
            shrunk_sigma = (
                math.sqrt(shrunk_var_num / shrunk_var_den)
                if shrunk_var_den > 0
                else sigma_global
            )

            # Prevent zero or near-zero variance
            if shrunk_sigma < 0.5:
                shrunk_sigma = 0.5

            judge_params[j_id] = (shrunk_mu, shrunk_sigma)
            judge_telemetry[str(j_id)] = {
                'raw_mean': round(s_bar, 2),
                'shrunk_mean': round(shrunk_mu, 2),
                'shrunk_std': round(shrunk_sigma, 2),
                'evaluations_count': n_j,
            }

        # 4. Project-Level Normalized Aggregation
        project_norm_scores: Dict[int, List[float]] = {}
        for e in evaluations:
            sub_id = e['submission_id']
            j_id = e['judge_id']
            raw_score = float(e['total_score'])

            mu_j, sigma_j = judge_params[j_id]
            z_score = (raw_score - mu_j) / sigma_j

            # Rescale normalized z-score back to standard 1.0 - 10.0 range
            rescaled = mu_global + z_score * sigma_global
            clamped = max(1.0, min(10.0, rescaled))
            project_norm_scores.setdefault(sub_id, []).append(clamped)

        # 5. Final Standings, Raw Means, and Standard Error
        submission_norm_scores: Dict[int, float] = {}
        submission_raw_scores: Dict[int, float] = {}
        submission_std_err: Dict[int, float] = {}

        for sub_id, norm_list in project_norm_scores.items():
            k = len(norm_list)
            avg_norm = sum(norm_list) / k
            submission_norm_scores[sub_id] = round(avg_norm, 2)

            raw_list = project_raw_scores.get(sub_id, [])
            submission_raw_scores[sub_id] = round(sum(raw_list) / len(raw_list), 2) if raw_list else 0.0

            if k > 1:
                sample_var = sum((x - avg_norm) ** 2 for x in norm_list) / (k - 1)
                se = math.sqrt(sample_var) / math.sqrt(k)
                submission_std_err[sub_id] = round(se, 3)
            else:
                # A single review carries no information about disagreement: report "unknown", not 0.
                submission_std_err[sub_id] = None

        return submission_norm_scores, submission_raw_scores, submission_std_err, judge_telemetry
