"""
Variable Review and Removal Service

Implements a 6-layer detection pipeline for identifying variables that should be removed:
- Layer 1: Identifier detection (row IDs, URLs, indices)
- Layer 2: Univariate signal screening (AUC, correlation)
- Layer 3: Pathological distribution patterns (zero-inflation, categorical mapping)
- Layer 4: Differential missingness
- Layer 5: Near-perfect separation (AUC >= 0.95)
- Layer 6: Correlation clustering with confirmed leakers

Design principle: No single statistical check auto-excludes a variable. 
Multiple converging signals are required for pre-selection.
"""

import json
import re
import time
import numpy as np
import pandas as pd
from scipy import stats
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ReasonBadge(str, Enum):
    """Classification badges for variable review results."""
    LEAKAGE = "Leakage"
    IDENTIFIER = "Identifier"
    LOW_VALUE = "Low-value"
    FLAGGED = "Flagged"
    CLEAN = "Clean"


@dataclass
class VariableFlags:
    """Stores all detection flags for a single variable."""
    
    # Layer 1 - Identifier detection
    high_cardinality: bool = False
    cardinality_ratio: float = 0.0
    name_pattern_match: bool = False
    matched_pattern: Optional[str] = None
    sequential_integers: bool = False
    identifier_signal_names: List[str] = field(default_factory=list)
    
    # Layer 2 - Univariate signal
    auc: Optional[float] = None
    correlation: Optional[float] = None
    high_univariate_signal: bool = False
    
    # Layer 3 - Pathological distributions
    zero_inflation_asymmetry: bool = False
    perfect_categorical_mapping: bool = False
    sentinel_details: List[str] = field(default_factory=list)
    categorical_mapping_detail: Optional[str] = None
    
    # Layer 4 - Differential missingness
    differential_missingness: bool = False
    extreme_missingness: bool = False
    null_rate_diff: float = 0.0
    null_rate_class0: float = 0.0
    null_rate_class1: float = 0.0
    
    # Layer 5 - Near-perfect separation
    near_perfect_auc: bool = False
    
    # Layer 6 - Correlation clustering
    correlated_with_leaker: bool = False
    correlated_leaker_name: Optional[str] = None
    correlation_with_leaker: float = 0.0
    correlation_method: Optional[str] = None
    
    # Low-value checks
    zero_variance: bool = False
    near_zero_variance: bool = False
    high_null_rate: bool = False
    null_rate: float = 0.0
    is_free_text: bool = False
    low_value_reason: Optional[str] = None
    
    # LLM Touchpoint results (TP1, TP2, TP3)
    llm_temporal_class: Optional[str] = None  # origination_attribute, behavioral_history, account_lifecycle, post_event
    llm_temporal_reasoning: Optional[str] = None
    llm_zero_inflation_reasoning: Optional[str] = None
    llm_missingness_reasoning: Optional[str] = None
    llm_is_post_event: bool = False  # True if LLM confirms variable is populated after target event


@dataclass
class VariableReviewResult:
    """Result of variable review for a single column."""
    column_name: str
    flags: VariableFlags
    reason_badge: ReasonBadge
    pre_selected: bool
    layer_flags: List[str] = field(default_factory=list)
    detail_reasons: List[str] = field(default_factory=list)


class VariableReviewPipeline:
    """
    6-layer variable review pipeline for detecting identifiers, leakage, and low-value variables.

    The public API and frontend payload remain stable, but the detection core uses:
    - binary target coercion when the target is truly two-class
    - richer semantic profiling for columns
    - cross-validated target encoding for binary categorical AUC
    - sentinel inflation checks beyond just zero
    - stronger Layer 6 correlation logic (Spearman + Cramer's V)
    """

    MIN_ROWS_FOR_STATS = 30
    MIN_CLASS_SIZE = 10
    CV_FOLDS = 5
    TARGET_ENCODE_MIN_SUPPORT = 30
    NULL_THRESHOLD = 0.95
    NEAR_ZERO_VARIANCE_THRESHOLD = 0.99
    ZERO_INFLATION_THRESHOLD = 0.95
    ZERO_INFLATION_OTHER_MAX = 0.50
    CATEGORICAL_PURITY_THRESHOLD = 0.95
    CATEGORICAL_LEVEL_COVERAGE = 0.80
    CATEGORICAL_ROW_COVERAGE = 0.50
    EXTREME_MISS_HIGH = 0.95
    EXTREME_MISS_LOW = 0.05
    MAX_CATEGORICAL_UNIQUE = 50
    NUMERIC_AS_CATEGORICAL_MAX_UNIQUE = 20
    FREE_TEXT_AVG_LEN_THRESHOLD = 50

    IDENTIFIER_TOKENS = [
        "id", "_id", "idx", "index", "key", "uuid", "url", "uri",
        "href", "rownum", "row_num", "serial", "seq", "row_id",
        "record_id", "obs_id", "observation_id", "guid", "hash",
        "token", "number", "pk", "fk",
        "email", "phone", "ssn", "ein", "sku", "barcode",
    ]
    IDENTIFIER_REGEX = re.compile(
        r"(?:^|_)(" + "|".join(re.escape(token) for token in IDENTIFIER_TOKENS) + r")(?:$|_)",
        re.IGNORECASE,
    )
    IDENTIFIER_EXACT = re.compile(
        r"^(" + "|".join(re.escape(token) for token in IDENTIFIER_TOKENS) + r")$",
        re.IGNORECASE,
    )
    HASH_LIKE_REGEX = re.compile(r"^[a-fA-F0-9\-]+$")
    SENTINEL_VALUES = {
        0, -1, -999, -9999, 999, 9999, -1.0, 99, -99,
        -888, -8888, 888, 8888, -777, -7777, 777, 7777,
    }

    def __init__(
        self,
        df: pd.DataFrame,
        target_col: str,
        protected_cols: Optional[List[str]] = None,
        auc_threshold: float = 0.70,
        near_perfect_auc_threshold: float = 0.95,
        correlation_threshold: float = 0.70,
        missingness_diff_threshold: float = 0.10,
        leaker_correlation_threshold: float = 0.85,
        data_dictionary: Optional[str] = None,
        enable_llm_reasoning: bool = True,
    ):
        self.df = df.copy()
        self.target_col = target_col
        self.protected_cols = set(protected_cols or [])
        self.protected_cols.add(target_col)

        self.auc_threshold = auc_threshold
        self.near_perfect_auc_threshold = near_perfect_auc_threshold
        self.correlation_threshold = correlation_threshold
        self.missingness_diff_threshold = missingness_diff_threshold
        self.leaker_correlation_threshold = leaker_correlation_threshold

        self.data_dictionary = data_dictionary
        self.enable_llm_reasoning = enable_llm_reasoning and bool(data_dictionary)
        self.variable_definitions: Dict[str, str] = {}
        self._llm_service = None
        self._rng = np.random.RandomState(42)

        self.results: Dict[str, VariableReviewResult] = {}
        self.pipeline_time_ms: float = 0.0
        self.target_type = "unknown"
        self.binary_target_mapping: Optional[Dict[Any, int]] = None
        self.column_profiles: Dict[str, Dict[str, Any]] = {}

        self._prepare_target()
        if self.data_dictionary:
            self._parse_data_dictionary()

        logger.info(
            "VariableReviewPipeline initialized: target=%s, type=%s, columns=%s, protected=%s, llm_enabled=%s",
            target_col,
            self.target_type,
            len(self.df.columns),
            len(self.protected_cols),
            self.enable_llm_reasoning,
        )

    # ========== TARGET PREPARATION ==========

    def _prepare_target(self) -> None:
        """Drop null target rows and coerce true binary targets to numeric 0/1."""
        if self.target_col not in self.df.columns:
            self.target_type = "unknown"
            return

        before = len(self.df)
        self.df = self.df.dropna(subset=[self.target_col]).reset_index(drop=True)
        dropped = before - len(self.df)
        if dropped > 0:
            logger.info(
                "Variable review dropped %s rows with null target (%0.1f%%)",
                dropped,
                (dropped / before * 100) if before else 0.0,
            )

        if len(self.df) == 0:
            self.target_type = "unknown"
            return

        series = self.df[self.target_col]
        nunique = series.nunique(dropna=True)

        if nunique == 2:
            coerced, mapping = self._coerce_binary_target(series)
            if coerced is not None:
                self.df[self.target_col] = coerced
                self.binary_target_mapping = mapping
                self.target_type = "binary"
                if mapping:
                    logger.info("Variable review coerced binary target with mapping: %s", mapping)
                return

        if nunique <= 10:
            self.target_type = "multiclass"
        else:
            self.target_type = "regression"

    def _coerce_binary_target(self, series: pd.Series) -> Tuple[Optional[pd.Series], Optional[Dict[Any, int]]]:
        """Coerce a two-class target to integer 0/1."""
        unique_vals = list(pd.Series(series.dropna().unique()))
        if len(unique_vals) != 2:
            return None, None

        val_set = set(unique_vals)
        if val_set == {0, 1} or val_set == {0.0, 1.0}:
            return series.astype(int), None

        if series.dtype == "bool" or val_set == {True, False}:
            return series.astype(int), None

        positive = {"yes", "true", "y", "1", "1.0", "t", "positive", "pos"}
        negative = {"no", "false", "n", "0", "0.0", "f", "negative", "neg"}
        str_vals = {str(v).strip().lower() for v in unique_vals}
        if str_vals & positive and str_vals & negative:
            mapping: Dict[Any, int] = {}
            for value in unique_vals:
                normalized = str(value).strip().lower()
                if normalized in positive:
                    mapping[value] = 1
                elif normalized in negative:
                    mapping[value] = 0
            if len(mapping) == 2:
                return series.map(mapping).astype(int), mapping

        sorted_vals = sorted(unique_vals, key=lambda value: str(value))
        mapping = {sorted_vals[0]: 0, sorted_vals[1]: 1}
        return series.map(mapping).astype(int), mapping

    # ========== DATA DICTIONARY PARSING ==========

    def _parse_data_dictionary(self) -> None:
        """
        Parse the data dictionary to extract variable definitions.
        Supports CSV/TSV-like content with variable name and description columns.
        """
        if not self.data_dictionary:
            return

        try:
            if "," in self.data_dictionary or "\t" in self.data_dictionary:
                delimiter = "\t" if "\t" in self.data_dictionary else ","
                lines = self.data_dictionary.strip().split("\n")
                if len(lines) < 2:
                    logger.warning("Data dictionary has no content rows")
                    return

                header = lines[0].lower().split(delimiter)
                name_col_idx = None
                desc_col_idx = None

                for i, col in enumerate(header):
                    cleaned = col.strip().strip('"').strip("'")
                    if cleaned in ("variable", "variable_name", "column", "column_name", "field", "name"):
                        name_col_idx = i
                    elif cleaned in ("description", "definition", "desc", "meaning", "explanation"):
                        desc_col_idx = i

                if name_col_idx is None:
                    name_col_idx = 0
                if desc_col_idx is None:
                    desc_col_idx = 1 if len(header) > 1 else 0

                for line in lines[1:]:
                    parts = line.split(delimiter)
                    if len(parts) <= max(name_col_idx, desc_col_idx):
                        continue
                    variable_name = parts[name_col_idx].strip().strip('"').strip("'")
                    description = parts[desc_col_idx].strip().strip('"').strip("'")
                    if variable_name:
                        self.variable_definitions[variable_name] = description

                logger.info(
                    "Parsed %s variable definitions from data dictionary",
                    len(self.variable_definitions),
                )
            else:
                logger.warning("Data dictionary format not recognized (expected CSV/TSV text)")
        except Exception as e:
            logger.warning("Failed to parse data dictionary: %s", e)

    def _get_llm_service(self):
        """Lazy load LLM service."""
        if self._llm_service is None:
            try:
                from app.services.llm_service import llm_service
                self._llm_service = llm_service
            except Exception as e:
                logger.warning("Failed to load LLM service: %s", e)
                self._llm_service = None
        return self._llm_service

    # ========== COLUMN PROFILING ==========

    def _profile_column(self, col: str) -> Dict[str, Any]:
        """Create a semantic profile used by all detection layers."""
        series = self.df[col]
        n = len(self.df)
        n_non_null = int(series.notna().sum())
        nunique = int(series.nunique(dropna=True))
        null_rate = float(series.isna().mean()) if n > 0 else 0.0

        cardinality_ratio = (nunique / n) if n > 0 else 0.0
        cardinality_ratio_non_null = (nunique / n_non_null) if n_non_null > 0 else 0.0

        if series.dtype == "bool":
            sem_type = "boolean"
        elif pd.api.types.is_datetime64_any_dtype(series):
            sem_type = "date"
        elif pd.api.types.is_numeric_dtype(series):
            if nunique <= 2:
                sem_type = "boolean"
            elif nunique <= self.NUMERIC_AS_CATEGORICAL_MAX_UNIQUE:
                sem_type = "numeric_categorical"
            else:
                sem_type = "numeric"
        elif series.dtype == "object" or pd.api.types.is_string_dtype(series):
            if nunique <= 2:
                sem_type = "boolean"
            elif nunique <= self.MAX_CATEGORICAL_UNIQUE:
                sem_type = "categorical"
            else:
                avg_len = series.dropna().astype(str).str.len().mean()
                sem_type = (
                    "free_text"
                    if pd.notna(avg_len) and avg_len > self.FREE_TEXT_AVG_LEN_THRESHOLD
                    else "high_cardinality_string"
                )
        else:
            sem_type = "other"

        return {
            "dtype": str(series.dtype),
            "sem_type": sem_type,
            "nunique": nunique,
            "null_rate": null_rate,
            "n_non_null": n_non_null,
            "cardinality_ratio": cardinality_ratio,
            "cardinality_ratio_non_null": cardinality_ratio_non_null,
        }

    def _is_integer_valued(self, series: pd.Series) -> bool:
        """Return True if a numeric series contains only integer-like values."""
        non_null = pd.to_numeric(series.dropna(), errors="coerce").dropna()
        if len(non_null) == 0:
            return False
        try:
            return bool(np.allclose(non_null, np.round(non_null), equal_nan=True))
        except Exception:
            return False

    def _is_hash_like(self, series: pd.Series, sample_size: int = 100) -> bool:
        """Detect UUID/hash-like strings based on fixed-length hex/alphanumeric patterns."""
        non_null = series.dropna().astype(str)
        if len(non_null) == 0:
            return False
        sample = non_null.sample(min(sample_size, len(non_null)), random_state=42)
        lengths = sample.str.len()
        if lengths.std() <= 1 and lengths.mean() >= 8:
            match_rate = sample.apply(lambda value: bool(self.HASH_LIKE_REGEX.match(value))).mean()
            return bool(match_rate > 0.90)
        return False

    # ========== LLM TOUCHPOINTS ==========

    def _run_llm_tp1(self, col: str, flags: VariableFlags) -> None:
        """Classify high-signal variables using data dictionary context."""
        if not self.enable_llm_reasoning or not flags.high_univariate_signal:
            return

        definition = self.variable_definitions.get(col)
        if not definition:
            return

        llm = self._get_llm_service()
        if not llm:
            return

        try:
            auc_display = f"{flags.auc:.3f}" if flags.auc is not None else "N/A"
            prompt = f"""You are analyzing a variable in a credit/loan dataset for potential data leakage.

Variable Name: {col}
Variable Definition: {definition}
Target Variable: {self.target_col}
AUC Score: {auc_display}

Based on the definition, classify this variable into ONE of these temporal categories:
1. origination_attribute: Information available at the time of application/origination (e.g., credit score at application, loan amount requested)
2. behavioral_history: Historical behavioral data before the prediction point (e.g., past payment history, previous delinquencies)
3. account_lifecycle: Information about the account's ongoing state (e.g., current balance, months on book)
4. post_event: Information that is only available AFTER the target event occurs (e.g., final loan status, charge-off amount) - THIS INDICATES LEAKAGE

Respond in JSON format:
{{"temporal_class": "<one of the 4 categories>", "reasoning": "<1-2 sentence explanation citing the definition>", "is_leakage_risk": <true/false>}}"""

            messages = [
                {"role": "system", "content": [{"type": "text", "text": "You are an expert in credit risk modeling and data leakage detection. Provide concise, accurate classifications."}]},
                {"role": "user", "content": [{"type": "text", "text": prompt}]},
            ]
            response = llm._call_chat_completion(context="data_treatment", messages=messages, temperature=0.1, max_tokens=300)
            response_text = llm._extract_response_text(response)
            if not response_text:
                return

            try:
                result = json.loads(response_text)
                flags.llm_temporal_class = result.get("temporal_class")
                flags.llm_temporal_reasoning = result.get("reasoning")
                if result.get("is_leakage_risk") and flags.llm_temporal_class == "post_event":
                    flags.llm_is_post_event = True
                logger.info("TP1 for %s: %s", col, flags.llm_temporal_class)
            except json.JSONDecodeError:
                response_lower = response_text.lower()
                for cat in ["post_event", "account_lifecycle", "behavioral_history", "origination_attribute"]:
                    if cat in response_lower:
                        flags.llm_temporal_class = cat
                        flags.llm_temporal_reasoning = response_text[:200]
                        if cat == "post_event":
                            flags.llm_is_post_event = True
                        break
        except Exception as e:
            logger.warning("TP1 LLM call failed for %s: %s", col, e)

    def _run_llm_tp2(self, col: str, flags: VariableFlags) -> None:
        """Ask the LLM whether sentinel/zero inflation looks post-event."""
        if not self.enable_llm_reasoning or not flags.zero_inflation_asymmetry:
            return

        definition = self.variable_definitions.get(col)
        if not definition:
            return

        llm = self._get_llm_service()
        if not llm:
            return

        try:
            prompt = f"""You are analyzing a variable for potential data leakage in a credit/loan dataset.

Variable Name: {col}
Variable Definition: {definition}
Target Variable: {self.target_col}
Observation: This variable shows strong sentinel/zero inflation asymmetry across target classes.

Question: Based on the definition, is this variable likely populated ONLY AFTER the target event occurs?
For example, a "charge_off_amount" would only have values after a loan defaults, making it a leakage variable.

Respond in JSON format:
{{"is_post_event": <true/false>, "reasoning": "<1-2 sentence explanation citing the definition>"}}"""

            messages = [
                {"role": "system", "content": [{"type": "text", "text": "You are an expert in credit risk modeling and data leakage detection."}]},
                {"role": "user", "content": [{"type": "text", "text": prompt}]},
            ]
            response = llm._call_chat_completion(context="data_treatment", messages=messages, temperature=0.1, max_tokens=200)
            response_text = llm._extract_response_text(response)
            if not response_text:
                return

            try:
                result = json.loads(response_text)
                flags.llm_zero_inflation_reasoning = result.get("reasoning")
                if result.get("is_post_event"):
                    flags.llm_is_post_event = True
                logger.info("TP2 for %s: is_post_event=%s", col, result.get("is_post_event"))
            except json.JSONDecodeError:
                flags.llm_zero_inflation_reasoning = response_text[:200]
                if "post" in response_text.lower() and ("event" in response_text.lower() or "target" in response_text.lower()):
                    flags.llm_is_post_event = True
        except Exception as e:
            logger.warning("TP2 LLM call failed for %s: %s", col, e)

    def _run_llm_tp3(self, col: str, flags: VariableFlags) -> None:
        """Ask the LLM whether differential missingness is causally tied to the outcome."""
        if not self.enable_llm_reasoning or not (flags.differential_missingness or flags.extreme_missingness):
            return

        definition = self.variable_definitions.get(col)
        if not definition:
            return

        llm = self._get_llm_service()
        if not llm:
            return

        try:
            prompt = f"""You are analyzing a variable for potential data leakage in a credit/loan dataset.

Variable Name: {col}
Variable Definition: {definition}
Target Variable: {self.target_col}
Observation: This variable shows differential missingness - the null rate differs significantly between target classes.
- Null rate for class 0: {flags.null_rate_class0:.1%}
- Null rate for class 1: {flags.null_rate_class1:.1%}
- Difference: {abs(flags.null_rate_diff):.1%}

Question: Based on the definition, is this differential missingness pattern likely CAUSALLY LINKED to the target outcome?
For example, if "days_past_due_at_default" is only populated for defaulted loans, the missingness itself reveals the outcome.

Respond in JSON format:
{{"is_causally_linked": <true/false>, "reasoning": "<1-2 sentence explanation citing the definition>"}}"""

            messages = [
                {"role": "system", "content": [{"type": "text", "text": "You are an expert in credit risk modeling and data leakage detection."}]},
                {"role": "user", "content": [{"type": "text", "text": prompt}]},
            ]
            response = llm._call_chat_completion(context="data_treatment", messages=messages, temperature=0.1, max_tokens=200)
            response_text = llm._extract_response_text(response)
            if not response_text:
                return

            try:
                result = json.loads(response_text)
                flags.llm_missingness_reasoning = result.get("reasoning")
                if result.get("is_causally_linked"):
                    flags.llm_is_post_event = True
                logger.info("TP3 for %s: is_causally_linked=%s", col, result.get("is_causally_linked"))
            except json.JSONDecodeError:
                flags.llm_missingness_reasoning = response_text[:200]
                lowered = response_text.lower()
                if ("causal" in lowered or "linked" in lowered) and ("yes" in lowered or "true" in lowered):
                    flags.llm_is_post_event = True
        except Exception as e:
            logger.warning("TP3 LLM call failed for %s: %s", col, e)

    # ========== LAYER 1: IDENTIFIER DETECTION ==========

    def _run_layer1(self, col: str, flags: VariableFlags) -> None:
        """Detect identifier-like variables using multiple converging signals."""
        profile = self.column_profiles[col]
        series = self.df[col]
        signals: List[str] = []

        cardinality_ratio = profile["cardinality_ratio_non_null"]
        flags.cardinality_ratio = cardinality_ratio

        is_continuous_float = (
            profile["sem_type"] == "numeric"
            and not self._is_integer_valued(series)
        )
        if cardinality_ratio > 0.95 and not is_continuous_float:
            flags.high_cardinality = True
            signals.append("high_cardinality")

        if self.IDENTIFIER_REGEX.search(col) or self.IDENTIFIER_EXACT.match(col):
            flags.name_pattern_match = True
            flags.matched_pattern = "identifier_name"
            signals.append("naming_pattern")

        if profile["sem_type"] in ("numeric", "numeric_categorical", "boolean"):
            non_null = series.dropna()
            if len(non_null) > 10 and self._is_integer_valued(non_null):
                sorted_vals = pd.to_numeric(non_null, errors="coerce").dropna().sort_values().reset_index(drop=True)
                diffs = sorted_vals.diff().dropna()
                if len(diffs) > 0:
                    if (diffs == 1).all():
                        flags.sequential_integers = True
                        signals.append("sequential")
                    elif (diffs > 0).all() and diffs.median() == 1:
                        flags.sequential_integers = True
                        signals.append("near_sequential")
                    elif (diffs > 0).all() or (diffs < 0).all():
                        flags.sequential_integers = True
                        signals.append("monotonic")

        if profile["sem_type"] in ("high_cardinality_string", "categorical") and self._is_hash_like(series):
            signals.append("hash_like")

        setattr(flags, "identifier_signal_names", signals)

    # ========== LAYER 2: UNIVARIATE SIGNAL ==========

    def _compute_auc_binary(self, x: np.ndarray, y: np.ndarray) -> Optional[float]:
        """Compute binary AUC via Mann-Whitney U with safety guards."""
        mask = np.isfinite(x)
        x = x[mask]
        y = y[mask]
        if len(x) < self.MIN_ROWS_FOR_STATS:
            return None

        n1 = int(np.sum(y == 1))
        n0 = int(np.sum(y == 0))
        if n1 < self.MIN_CLASS_SIZE or n0 < self.MIN_CLASS_SIZE:
            return None
        if len(np.unique(x)) < 2:
            return None

        try:
            u_stat, _ = stats.mannwhitneyu(x[y == 1], x[y == 0], alternative="two-sided")
            auc = u_stat / (n1 * n0)
            return float(max(auc, 1 - auc))
        except Exception:
            return None

    def _cv_target_encode(self, col: str) -> pd.Series:
        """Cross-validated target encoding for binary categorical AUC screening."""
        encoded = pd.Series(np.nan, index=self.df.index, dtype=float)
        global_mean = float(self.df[self.target_col].mean())
        n_folds = max(2, min(self.CV_FOLDS, len(self.df)))
        fold_ids = self._rng.randint(0, n_folds, size=len(self.df))

        for fold in range(n_folds):
            train_mask = fold_ids != fold
            test_mask = fold_ids == fold
            if not test_mask.any():
                continue

            train_df = self.df.loc[train_mask, [col, self.target_col]]
            grouped = train_df.groupby(col, dropna=False)[self.target_col].agg(["mean", "count"])
            min_support = max(self.TARGET_ENCODE_MIN_SUPPORT, int(len(train_df) * 0.001))
            smoothed = grouped.apply(
                lambda row: row["mean"] if row["count"] >= min_support else global_mean,
                axis=1,
            )

            fold_encoded = self.df.loc[test_mask, col].map(smoothed).fillna(global_mean)
            encoded.loc[test_mask] = fold_encoded.astype(float)

        return encoded.fillna(global_mean)

    def _map_boolean_series(self, series: pd.Series) -> Optional[pd.Series]:
        """Map a boolean-like series to float values for AUC calculation."""
        if series.dtype == "bool":
            return series.astype(float)
        try:
            numeric = pd.to_numeric(series, errors="coerce")
            unique_vals = set(pd.Series(numeric.dropna().unique()).astype(float))
            if unique_vals and unique_vals.issubset({0.0, 1.0}):
                return numeric.astype(float)
        except Exception:
            pass

        values = list(pd.Series(series.dropna().unique()))
        if len(values) != 2:
            return None
        mapping = {values[0]: 0.0, values[1]: 1.0}
        try:
            return series.map(mapping).astype(float)
        except Exception:
            return None

    def _compute_binary_auc_for_column(self, col: str) -> Optional[float]:
        """Compute binary AUC using semantic typing and leakage-safe encodings."""
        profile = self.column_profiles[col]
        if profile["null_rate"] >= self.NULL_THRESHOLD or profile["nunique"] <= 1:
            return None
        if len(self.df) < self.MIN_ROWS_FOR_STATS:
            return None

        series = self.df[col]
        y = self.df[self.target_col].astype(int).values
        sem_type = profile["sem_type"]

        try:
            if sem_type == "boolean":
                mapped = self._map_boolean_series(series)
                if mapped is None:
                    return None
                x = mapped.values.astype(float)
            elif sem_type == "date":
                converted = pd.to_datetime(series, errors="coerce")
                ref = converted.dropna().min()
                if pd.isna(ref):
                    return None
                x = (converted - ref).dt.total_seconds().values.astype(float)
            elif sem_type == "numeric":
                x = pd.to_numeric(series, errors="coerce").values.astype(float)
            elif sem_type in ("categorical", "numeric_categorical", "high_cardinality_string"):
                x = self._cv_target_encode(col).values.astype(float)
            else:
                return None
        except Exception:
            return None

        auc = self._compute_auc_binary(x, y)
        return round(auc, 4) if auc is not None else None

    def _compute_auc_multiclass(self, col: str) -> Optional[float]:
        """Weighted one-vs-rest AUC for numeric multiclass targets."""
        mask = self.df[col].notna() & self.df[self.target_col].notna()
        x = self.df.loc[mask, col]
        y = self.df.loc[mask, self.target_col]

        try:
            x = pd.to_numeric(x, errors="coerce").dropna()
            y = y.loc[x.index]
        except Exception:
            return None

        if len(x) == 0:
            return None

        weighted_auc_sum = 0.0
        total_weight = 0.0
        for class_value in y.unique():
            y_binary = (y == class_value).astype(int)
            n0 = int((y_binary == 0).sum())
            n1 = int((y_binary == 1).sum())
            if n0 == 0 or n1 == 0:
                continue
            try:
                u_stat, _ = stats.mannwhitneyu(x[y_binary == 1], x[y_binary == 0], alternative="two-sided")
                auc = u_stat / (n1 * n0)
                auc = max(auc, 1 - auc)
                weight = n1 / len(y)
                weighted_auc_sum += auc * weight
                total_weight += weight
            except Exception:
                continue

        if total_weight == 0:
            return None
        return float(weighted_auc_sum / total_weight)

    def _compute_correlation(self, col: str) -> Optional[float]:
        """Absolute Pearson correlation for regression targets."""
        mask = self.df[col].notna() & self.df[self.target_col].notna()
        if mask.sum() < 3:
            return None
        try:
            x = pd.to_numeric(self.df.loc[mask, col], errors="coerce")
            y = pd.to_numeric(self.df.loc[mask, self.target_col], errors="coerce")
            valid_mask = x.notna() & y.notna()
            if valid_mask.sum() < 3:
                return None
            return float(abs(x[valid_mask].corr(y[valid_mask])))
        except Exception:
            return None

    def _run_layer2(self, col: str, flags: VariableFlags) -> None:
        """Run univariate signal screening."""
        profile = self.column_profiles[col]

        if self.target_type == "binary":
            flags.auc = self._compute_binary_auc_for_column(col)
            flags.high_univariate_signal = flags.auc is not None and flags.auc >= self.auc_threshold
            return

        is_numeric = pd.api.types.is_numeric_dtype(self.df[col])
        if is_numeric and self.target_type == "multiclass":
            flags.auc = self._compute_auc_multiclass(col)
            flags.high_univariate_signal = flags.auc is not None and flags.auc >= self.auc_threshold
        elif is_numeric and self.target_type == "regression":
            flags.correlation = self._compute_correlation(col)
            flags.high_univariate_signal = (
                flags.correlation is not None and flags.correlation >= self.correlation_threshold
            )
        elif self.target_type == "multiclass" and profile["sem_type"] in ("categorical", "numeric_categorical", "boolean"):
            try:
                encoded = self.df.groupby(col)[self.target_col].transform(lambda values: values.mode().iloc[0] if len(values.mode()) > 0 else np.nan)
                encoded_num = pd.factorize(encoded)[0].astype(float)
                target_num = pd.factorize(self.df[self.target_col])[0].astype(float)
                corr = np.corrcoef(encoded_num, target_num)[0, 1]
                if np.isfinite(corr):
                    flags.correlation = float(abs(corr))
                    flags.high_univariate_signal = flags.correlation >= self.correlation_threshold
            except Exception:
                pass

    # ========== LAYER 3: PATHOLOGICAL DISTRIBUTIONS ==========

    def _detect_sentinel_inflation(self, col: str, sentinel_values: set) -> List[str]:
        """Return details for any sentinel values disproportionately concentrated in one class."""
        series = self.df[col]
        target = self.df[self.target_col]
        details: List[str] = []

        for sentinel in sentinel_values:
            is_sentinel = series == sentinel
            if int(is_sentinel.sum()) < 10:
                continue

            rate0 = float(is_sentinel[target == 0].mean()) if (target == 0).any() else 0.0
            rate1 = float(is_sentinel[target == 1].mean()) if (target == 1).any() else 0.0

            if rate0 >= self.ZERO_INFLATION_THRESHOLD and rate1 < self.ZERO_INFLATION_OTHER_MAX:
                details.append(f"Sentinel {sentinel}: class0={rate0:.3f}, class1={rate1:.3f}")
            elif rate1 >= self.ZERO_INFLATION_THRESHOLD and rate0 < self.ZERO_INFLATION_OTHER_MAX:
                details.append(f"Sentinel {sentinel}: class0={rate0:.3f}, class1={rate1:.3f}")

        return details

    def _categorical_purity_detail(self, col: str) -> Optional[str]:
        """Return a detail string when categorical/numeric-categorical levels are highly pure."""
        profile = self.column_profiles[col]
        sem_type = profile["sem_type"]
        if sem_type not in ("categorical", "numeric_categorical", "boolean"):
            return None
        if profile["nunique"] <= 1:
            return None

        grouped = self.df.groupby(col, dropna=False)[self.target_col].agg(["mean", "count"])
        grouped.columns = ["rate", "count"]
        pure_mask = (grouped["rate"] > self.CATEGORICAL_PURITY_THRESHOLD) | (
            grouped["rate"] < (1 - self.CATEGORICAL_PURITY_THRESHOLD)
        )
        n_levels = len(grouped)
        if n_levels == 0:
            return None

        n_pure_levels = int(pure_mask.sum())
        level_coverage = n_pure_levels / n_levels
        row_coverage = float(grouped.loc[pure_mask, "count"].sum() / grouped["count"].sum())

        if level_coverage > self.CATEGORICAL_LEVEL_COVERAGE:
            return (
                f"Categorical mapping: {level_coverage:.0%} of levels have >"
                f"{self.CATEGORICAL_PURITY_THRESHOLD:.0%} purity ({row_coverage:.0%} of rows)"
            )
        if row_coverage > self.CATEGORICAL_ROW_COVERAGE:
            return (
                f"Categorical mapping: {row_coverage:.0%} of rows fall in levels with >"
                f"{self.CATEGORICAL_PURITY_THRESHOLD:.0%} purity ({n_pure_levels}/{n_levels} levels)"
            )
        return None

    def _run_layer3(self, col: str, flags: VariableFlags) -> None:
        """Detect sentinel inflation and near-perfect categorical mapping."""
        if self.target_type != "binary":
            return

        profile = self.column_profiles[col]
        if profile["null_rate"] >= self.NULL_THRESHOLD or profile["nunique"] <= 1:
            return

        series = self.df[col]
        if pd.api.types.is_numeric_dtype(series):
            sentinel_details = self._detect_sentinel_inflation(col, self.SENTINEL_VALUES)
            try:
                mode_series = series.mode(dropna=True)
                if len(mode_series) > 0:
                    mode_value = mode_series.iloc[0]
                    if mode_value not in self.SENTINEL_VALUES:
                        sentinel_details.extend(self._detect_sentinel_inflation(col, {mode_value}))
            except Exception:
                pass

            if sentinel_details:
                flags.zero_inflation_asymmetry = True
                setattr(flags, "sentinel_details", sentinel_details)

        mapping_detail = self._categorical_purity_detail(col)
        if mapping_detail:
            flags.perfect_categorical_mapping = True
            setattr(flags, "categorical_mapping_detail", mapping_detail)

    # ========== LAYER 4: DIFFERENTIAL MISSINGNESS ==========

    def _run_layer4(self, col: str, flags: VariableFlags) -> None:
        """Detect target-dependent missingness patterns."""
        if self.target_type != "binary":
            return

        profile = self.column_profiles[col]
        if profile["null_rate"] == 0.0 or profile["null_rate"] >= self.NULL_THRESHOLD:
            return

        try:
            null_rate_0 = float(self.df.loc[self.df[self.target_col] == 0, col].isna().mean())
            null_rate_1 = float(self.df.loc[self.df[self.target_col] == 1, col].isna().mean())
            flags.null_rate_class0 = null_rate_0
            flags.null_rate_class1 = null_rate_1
            flags.null_rate_diff = abs(null_rate_0 - null_rate_1)

            if flags.null_rate_diff >= self.missingness_diff_threshold:
                flags.differential_missingness = True

            if (
                (null_rate_0 >= self.EXTREME_MISS_HIGH and null_rate_1 <= self.EXTREME_MISS_LOW)
                or (null_rate_1 >= self.EXTREME_MISS_HIGH and null_rate_0 <= self.EXTREME_MISS_LOW)
            ):
                flags.extreme_missingness = True
        except Exception:
            pass

    # ========== LAYER 5: NEAR-PERFECT SEPARATION ==========

    def _run_layer5(self, flags: VariableFlags) -> None:
        """Flag near-perfect univariate separation."""
        if flags.auc is not None and flags.auc >= self.near_perfect_auc_threshold:
            flags.near_perfect_auc = True

    # ========== LAYER 6: CORRELATION CLUSTERING ==========

    def _cramers_v(self, x: pd.Series, y: pd.Series) -> Optional[float]:
        """Compute Cramer's V for two categorical series."""
        try:
            confusion = pd.crosstab(x, y)
            n = confusion.to_numpy().sum()
            if n == 0:
                return None
            chi2 = 0.0
            row_sums = confusion.sum(axis=1)
            col_sums = confusion.sum(axis=0)
            for i in confusion.index:
                for j in confusion.columns:
                    expected = row_sums[i] * col_sums[j] / n
                    if expected > 0:
                        chi2 += (confusion.loc[i, j] - expected) ** 2 / expected
            r, k = confusion.shape
            denom = n * (min(r, k) - 1)
            if denom == 0:
                return None
            return float(np.sqrt(chi2 / denom))
        except Exception:
            return None

    def _run_layer6(self, confirmed_leakers: List[str]) -> None:
        """Find variables associated with confirmed leakers via numeric and categorical similarity."""
        if not confirmed_leakers:
            return

        numeric_candidates = [
            col for col in self.column_profiles
            if pd.api.types.is_numeric_dtype(self.df[col])
            and self.column_profiles[col]["nunique"] > 1
            and self.column_profiles[col]["null_rate"] < self.NULL_THRESHOLD
            and col not in confirmed_leakers
        ]
        numeric_leakers = [
            col for col in confirmed_leakers
            if col in self.df.columns
            and pd.api.types.is_numeric_dtype(self.df[col])
            and self.column_profiles.get(col, {}).get("nunique", 0) > 1
        ]

        for col in numeric_candidates:
            flags = self.results.get(col).flags if col in self.results else None
            if not flags:
                continue
            for leaker in numeric_leakers:
                try:
                    mask = self.df[col].notna() & self.df[leaker].notna()
                    if int(mask.sum()) < self.MIN_ROWS_FOR_STATS:
                        continue
                    rho, _ = stats.spearmanr(self.df.loc[mask, col], self.df.loc[mask, leaker])
                    rho = abs(float(rho))
                    if np.isfinite(rho) and rho > self.leaker_correlation_threshold:
                        flags.correlated_with_leaker = True
                        flags.correlated_leaker_name = leaker
                        flags.correlation_with_leaker = rho
                        setattr(flags, "correlation_method", "Spearman")
                        break
                except Exception:
                    continue

        categorical_candidates = [
            col for col, profile in self.column_profiles.items()
            if profile["sem_type"] in ("categorical", "numeric_categorical", "boolean")
            and profile["nunique"] > 1
            and col not in confirmed_leakers
        ]
        categorical_leakers = [
            col for col in confirmed_leakers
            if self.column_profiles.get(col, {}).get("sem_type") in ("categorical", "numeric_categorical", "boolean")
            and self.column_profiles.get(col, {}).get("nunique", 0) > 1
        ]

        for col in categorical_candidates:
            flags = self.results.get(col).flags if col in self.results else None
            if not flags or flags.correlated_with_leaker:
                continue
            for leaker in categorical_leakers:
                association = self._cramers_v(self.df[col], self.df[leaker])
                if association is not None and association > self.leaker_correlation_threshold:
                    flags.correlated_with_leaker = True
                    flags.correlated_leaker_name = leaker
                    flags.correlation_with_leaker = association
                    setattr(flags, "correlation_method", "Cramer's V")
                    break

    # ========== LOW-VALUE CHECKS ==========

    def _run_low_value_checks(self, col: str, flags: VariableFlags) -> None:
        """Check constant, mostly-null, near-zero variance, and free-text columns."""
        profile = self.column_profiles[col]
        flags.null_rate = profile["null_rate"]

        if profile["nunique"] == 0 or flags.null_rate >= 1.0:
            flags.high_null_rate = True
            setattr(flags, "low_value_reason", "100% null")
            return

        if profile["nunique"] <= 1 and flags.null_rate > 0:
            flags.zero_variance = True
            setattr(flags, "low_value_reason", "Single value + nulls only")
            return

        if profile["nunique"] <= 1:
            flags.zero_variance = True
            setattr(flags, "low_value_reason", "Constant")
            return

        if flags.null_rate >= self.NULL_THRESHOLD:
            flags.high_null_rate = True
            setattr(flags, "low_value_reason", f">{self.NULL_THRESHOLD:.0%} null")
            return

        if profile["sem_type"] in ("numeric", "numeric_categorical", "boolean"):
            try:
                top_freq = float(self.df[col].value_counts(normalize=True, dropna=False).iloc[0])
                if top_freq > self.NEAR_ZERO_VARIANCE_THRESHOLD:
                    flags.near_zero_variance = True
                    setattr(flags, "low_value_reason", f"Near-zero variance ({top_freq:.1%} single value)")
                    return
            except Exception:
                pass

        if profile["sem_type"] == "free_text":
            flags.is_free_text = True
            setattr(flags, "low_value_reason", "Free-text / unstructured")

    # ========== ADJUDICATION ==========

    def _append_llm_details(self, flags: VariableFlags, detail_reasons: List[str]) -> None:
        if flags.llm_temporal_reasoning:
            detail_reasons.append(f"LLM Analysis: {flags.llm_temporal_reasoning}")
        if flags.llm_zero_inflation_reasoning:
            detail_reasons.append(f"LLM Analysis: {flags.llm_zero_inflation_reasoning}")
        if flags.llm_missingness_reasoning:
            detail_reasons.append(f"LLM Analysis: {flags.llm_missingness_reasoning}")

    def _adjudicate(self, flags: VariableFlags, column_name: str = "") -> Tuple[ReasonBadge, bool, List[str], List[str]]:
        """Classify a variable and decide whether to pre-select it for removal."""
        detail_reasons: List[str] = []
        layer_flags: List[str] = []

        identifier_signals = list(getattr(flags, "identifier_signal_names", []))
        l1_signal_count = len(identifier_signals)
        if l1_signal_count > 0:
            layer_flags.append(f"L1 (x{l1_signal_count})" if l1_signal_count > 1 else "L1")

        if flags.high_univariate_signal:
            layer_flags.append("L2")
        if flags.zero_inflation_asymmetry or flags.perfect_categorical_mapping:
            layer_flags.append("L3")
        if flags.differential_missingness or flags.extreme_missingness:
            layer_flags.append("L4")
        if flags.near_perfect_auc:
            layer_flags.append("L5")
        if flags.correlated_with_leaker:
            layer_flags.append("L6")

        if getattr(flags, "low_value_reason", None):
            detail_reasons.append(str(getattr(flags, "low_value_reason")))
            if flags.high_null_rate:
                detail_reasons.append("Too few valid observations to provide reliable signal")
            elif flags.zero_variance:
                detail_reasons.append("Provides no discriminative information for prediction")
            elif flags.near_zero_variance:
                detail_reasons.append("Insufficient variation to contribute meaningful predictive power")
            elif flags.is_free_text:
                detail_reasons.append("High-cardinality long-form text is not suitable for this tabular review")
            return ReasonBadge.LOW_VALUE, False, ["Low-value"], detail_reasons

        if l1_signal_count >= 2 or (l1_signal_count == 1 and flags.cardinality_ratio > 0.99):
            if flags.high_cardinality:
                detail_reasons.append(
                    f"High cardinality among non-null rows: {flags.cardinality_ratio:.1%} unique values"
                )
            if flags.name_pattern_match:
                detail_reasons.append(f"Column name '{column_name}' matches common identifier naming patterns")
            if flags.sequential_integers:
                detail_reasons.append("Monotonic / sequential integer structure is typical of row identifiers")
            if "hash_like" in identifier_signals:
                detail_reasons.append("Values appear hash/UUID-like, which is common for surrogate identifiers")
            return ReasonBadge.IDENTIFIER, True, layer_flags, detail_reasons

        if flags.near_perfect_auc:
            detail_reasons.append(
                f"AUC = {flags.auc:.3f}, suspiciously high predictive power that likely embeds target information"
            )
            for detail in getattr(flags, "sentinel_details", []):
                detail_reasons.append(detail)
            if getattr(flags, "categorical_mapping_detail", None):
                detail_reasons.append(str(getattr(flags, "categorical_mapping_detail")))
            if flags.correlated_with_leaker and flags.correlated_leaker_name:
                method = getattr(flags, "correlation_method", "Association")
                detail_reasons.append(
                    f"{method}={flags.correlation_with_leaker:.3f} with confirmed leaker '{flags.correlated_leaker_name}'"
                )
            return ReasonBadge.LEAKAGE, True, layer_flags, detail_reasons

        has_l2 = flags.high_univariate_signal
        has_l3_mapping = flags.perfect_categorical_mapping
        has_l3_sentinel = flags.zero_inflation_asymmetry
        has_l3 = has_l3_mapping or has_l3_sentinel
        has_l4 = flags.differential_missingness or flags.extreme_missingness

        if has_l2 and has_l3:
            if flags.auc is not None:
                detail_reasons.append(f"High univariate signal: AUC = {flags.auc:.3f}")
            for detail in getattr(flags, "sentinel_details", []):
                detail_reasons.append(detail)
            if getattr(flags, "categorical_mapping_detail", None):
                detail_reasons.append(str(getattr(flags, "categorical_mapping_detail")))
            return ReasonBadge.LEAKAGE, True, layer_flags, detail_reasons

        if has_l2 and has_l4:
            if flags.auc is not None:
                detail_reasons.append(f"High univariate signal: AUC = {flags.auc:.3f}")
            detail_reasons.append(
                f"Missingness differs by target: class0={flags.null_rate_class0:.3f}, "
                f"class1={flags.null_rate_class1:.3f}, diff={flags.null_rate_diff:.3f}"
            )
            return ReasonBadge.LEAKAGE, True, layer_flags, detail_reasons

        if has_l3_mapping:
            if flags.auc is not None and flags.auc >= 0.60:
                detail_reasons.append(str(getattr(flags, "categorical_mapping_detail", "Categorical mapping is highly pure by target")))
                return ReasonBadge.LEAKAGE, True, layer_flags, detail_reasons
            if getattr(flags, "categorical_mapping_detail", "").startswith("Categorical mapping:"):
                detail_reasons.append(str(getattr(flags, "categorical_mapping_detail")))
                return ReasonBadge.LEAKAGE, True, layer_flags, detail_reasons

        if has_l3_sentinel and flags.auc is not None and flags.auc >= 0.60:
            detail_reasons.extend(getattr(flags, "sentinel_details", []))
            return ReasonBadge.LEAKAGE, True, layer_flags, detail_reasons

        if flags.extreme_missingness:
            detail_reasons.append(
                "Extreme missingness pattern: null behavior nearly encodes the outcome by itself"
            )
            return ReasonBadge.LEAKAGE, True, layer_flags, detail_reasons

        if flags.correlated_with_leaker and flags.correlated_leaker_name:
            method = getattr(flags, "correlation_method", "Association")
            detail_reasons.append(
                f"{method}={flags.correlation_with_leaker:.3f} with confirmed leaker '{flags.correlated_leaker_name}'"
            )
            return ReasonBadge.LEAKAGE, True, layer_flags, detail_reasons

        any_flag = any([
            has_l2,
            has_l3_sentinel,
            has_l3_mapping,
            flags.differential_missingness,
            flags.extreme_missingness,
            l1_signal_count == 1,
        ])
        if any_flag:
            if has_l2:
                metric = flags.auc if flags.auc is not None else flags.correlation
                if metric is not None:
                    detail_reasons.append(
                        f"Elevated univariate signal ({'AUC' if flags.auc is not None else 'correlation'} = {metric:.3f})"
                    )
            for detail in getattr(flags, "sentinel_details", []):
                detail_reasons.append(detail)
            if getattr(flags, "categorical_mapping_detail", None):
                detail_reasons.append(str(getattr(flags, "categorical_mapping_detail")))
            if flags.differential_missingness:
                detail_reasons.append(
                    f"Differential missingness: class0={flags.null_rate_class0:.3f}, "
                    f"class1={flags.null_rate_class1:.3f}, diff={flags.null_rate_diff:.3f}"
                )
            if l1_signal_count == 1:
                detail_reasons.append(f"Single identifier signal detected: {identifier_signals[0]}")
            return ReasonBadge.FLAGGED, False, layer_flags, detail_reasons

        return ReasonBadge.CLEAN, False, [], []

    def _format_layer_flags(self, flags: VariableFlags) -> str:
        """Format layer flags for compact frontend display."""
        layers: List[str] = []
        l1_count = len(getattr(flags, "identifier_signal_names", []))
        if l1_count > 0:
            layers.append(f"L1 (x{l1_count})" if l1_count > 1 else "L1")
        if flags.high_univariate_signal:
            layers.append("L2")
        if flags.zero_inflation_asymmetry or flags.perfect_categorical_mapping:
            layers.append("L3")
        if flags.differential_missingness or flags.extreme_missingness:
            layers.append("L4")
        if flags.near_perfect_auc:
            layers.append("L5")
        if flags.correlated_with_leaker:
            layers.append("L6")
        if getattr(flags, "low_value_reason", None) and not layers:
            layers.append("Low-value")
        return ", ".join(layers) if layers else "--"

    # ========== SORTING ==========

    def _sort_results(self) -> List[VariableReviewResult]:
        """Sort results with pre-selected leakage first, then flagged, then clean."""
        results_list = list(self.results.values())

        def sort_key(result: VariableReviewResult):
            if result.pre_selected:
                severity_order = {
                    ReasonBadge.LEAKAGE: 0,
                    ReasonBadge.IDENTIFIER: 1,
                    ReasonBadge.LOW_VALUE: 2,
                }
                severity = severity_order.get(result.reason_badge, 3)
                score = result.flags.auc or result.flags.correlation or 0
                return (0, severity, -score, result.column_name)
            if result.reason_badge == ReasonBadge.FLAGGED:
                score = result.flags.auc or result.flags.correlation or 0
                return (1, 0, -score, result.column_name)
            if result.reason_badge == ReasonBadge.LOW_VALUE:
                return (2, 0, 0, result.column_name)
            return (3, 0, 0, result.column_name)

        return sorted(results_list, key=sort_key)

    # ========== MAIN PIPELINE ==========

    def run(self) -> List[VariableReviewResult]:
        """Run the full 6-layer variable review pipeline with LLM touchpoints."""
        start_time = time.time()
        columns = [col for col in self.df.columns if col not in self.protected_cols]
        self.column_profiles = {col: self._profile_column(col) for col in columns}

        logger.info("Running variable review on %s columns", len(columns))

        for col in columns:
            flags = VariableFlags()

            try:
                self._run_layer1(col, flags)
                self._run_layer2(col, flags)
                if flags.high_univariate_signal and self.enable_llm_reasoning:
                    self._run_llm_tp1(col, flags)

                self._run_layer3(col, flags)
                if flags.zero_inflation_asymmetry and self.enable_llm_reasoning:
                    self._run_llm_tp2(col, flags)

                self._run_layer4(col, flags)
                if (flags.differential_missingness or flags.extreme_missingness) and self.enable_llm_reasoning:
                    self._run_llm_tp3(col, flags)

                self._run_layer5(flags)
                self._run_low_value_checks(col, flags)
            except Exception as e:
                logger.warning("Error processing column %s: %s", col, e)
                continue

            reason_badge, pre_selected, layer_flags, detail_reasons = self._adjudicate(flags, column_name=col)
            self._append_llm_details(flags, detail_reasons)

            if flags.llm_is_post_event and reason_badge != ReasonBadge.LEAKAGE:
                reason_badge = ReasonBadge.LEAKAGE
                pre_selected = True
                if "LLM" not in layer_flags:
                    layer_flags.append("LLM")
                detail_reasons.append(
                    "LLM confirmed this variable is populated after the target event (post-event leakage)"
                )

            self.results[col] = VariableReviewResult(
                column_name=col,
                flags=flags,
                reason_badge=reason_badge,
                pre_selected=pre_selected,
                layer_flags=layer_flags,
                detail_reasons=detail_reasons,
            )

        confirmed_leakers = [
            col for col, result in self.results.items()
            if result.reason_badge == ReasonBadge.LEAKAGE
        ]
        logger.info("Phase 1 complete: %s confirmed leakers", len(confirmed_leakers))

        self._run_layer6(confirmed_leakers)

        for col in columns:
            result = self.results.get(col)
            if not result or not result.flags.correlated_with_leaker or result.reason_badge == ReasonBadge.LEAKAGE:
                continue

            result.reason_badge = ReasonBadge.LEAKAGE
            result.pre_selected = True
            if "L6" not in result.layer_flags:
                result.layer_flags.append("L6")
            method = getattr(result.flags, "correlation_method", "Association")
            result.detail_reasons.append(
                f"{method}={result.flags.correlation_with_leaker:.3f} with leaker: {result.flags.correlated_leaker_name}"
            )

        self.pipeline_time_ms = (time.time() - start_time) * 1000
        sorted_results = self._sort_results()

        pre_selected_count = sum(1 for result in sorted_results if result.pre_selected)
        flagged_count = sum(1 for result in sorted_results if result.reason_badge == ReasonBadge.FLAGGED)
        clean_count = sum(1 for result in sorted_results if result.reason_badge == ReasonBadge.CLEAN)
        logger.info(
            "Variable review complete in %.1fms: %s pre-selected, %s flagged, %s clean",
            self.pipeline_time_ms,
            pre_selected_count,
            flagged_count,
            clean_count,
        )
        return sorted_results

    def format_for_frontend(self, results: List[VariableReviewResult]) -> Dict[str, Any]:
        """Format results for frontend table display."""
        rows = []
        for result in results:
            if result.flags.auc is not None:
                auc_display = f"{result.flags.auc:.2f}"
            elif result.flags.correlation is not None:
                auc_display = f"{result.flags.correlation:.2f}"
            else:
                auc_display = "--"

            flags_display = self._format_layer_flags(result.flags)
            if result.pre_selected:
                row_class = "row-preselected"
            elif result.reason_badge == ReasonBadge.FLAGGED:
                row_class = "row-flagged"
            else:
                row_class = "row-clean"

            rows.append({
                "variable": result.column_name,
                "auc": auc_display,
                "auc_value": result.flags.auc or result.flags.correlation,
                "flags": flags_display,
                "reason": result.reason_badge.value,
                "pre_selected": result.pre_selected,
                "row_class": row_class,
                "detail_reasons": result.detail_reasons,
                "layer_flags": result.layer_flags,
                "cardinality_ratio": result.flags.cardinality_ratio,
                "null_rate": result.flags.null_rate,
                "null_rate_diff": result.flags.null_rate_diff,
            })

        return {
            "rows": rows,
            "summary": {
                "total": len(rows),
                "pre_selected": sum(1 for result in results if result.pre_selected),
                "flagged": sum(1 for result in results if result.reason_badge == ReasonBadge.FLAGGED),
                "clean": sum(1 for result in results if result.reason_badge == ReasonBadge.CLEAN),
            },
            "pipeline_time_ms": self.pipeline_time_ms,
        }


class VariableReviewService:
    """Service class for variable review operations."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def run_variable_review(
        self,
        df: pd.DataFrame,
        target_col: str,
        sample_id_col: Optional[str] = None,
        weight_col: Optional[str] = None,
        auc_threshold: float = 0.70,
        near_perfect_auc_threshold: float = 0.95,
        correlation_threshold: float = 0.70,
        missingness_diff_threshold: float = 0.10,
        leaker_correlation_threshold: float = 0.85,
        data_dictionary: Optional[str] = None,
        enable_llm_reasoning: bool = True,
    ) -> Dict[str, Any]:
        """
        Run the 6-layer variable review pipeline with optional LLM reasoning.
        
        Args:
            df: DataFrame to analyze
            target_col: Target variable column name
            sample_id_col: Sample identifier column (excluded from review)
            weight_col: Weight column (excluded from review)
            auc_threshold: Threshold for flagging high AUC (default 0.70)
            near_perfect_auc_threshold: Threshold for near-perfect AUC (default 0.95)
            correlation_threshold: Threshold for high correlation (default 0.70)
            missingness_diff_threshold: Threshold for differential missingness (default 0.10)
            leaker_correlation_threshold: Threshold for correlation with leaker (default 0.85)
            data_dictionary: CSV content of data dictionary for LLM reasoning
            enable_llm_reasoning: Whether to enable LLM touchpoints (TP1, TP2, TP3)
        
        Returns:
            Dictionary with rows, summary, and pipeline_time_ms
        """
        # Build protected columns list
        protected = [target_col]
        if sample_id_col:
            protected.append(sample_id_col)
        if weight_col:
            protected.append(weight_col)
        
        # Run pipeline
        pipeline = VariableReviewPipeline(
            df=df,
            target_col=target_col,
            protected_cols=protected,
            auc_threshold=auc_threshold,
            near_perfect_auc_threshold=near_perfect_auc_threshold,
            correlation_threshold=correlation_threshold,
            missingness_diff_threshold=missingness_diff_threshold,
            leaker_correlation_threshold=leaker_correlation_threshold,
            data_dictionary=data_dictionary,
            enable_llm_reasoning=enable_llm_reasoning,
        )
        
        results = pipeline.run()
        return pipeline.format_for_frontend(results)
    
    def apply_variable_removal(
        self,
        df: pd.DataFrame,
        variables_to_remove: List[str],
    ) -> pd.DataFrame:
        """
        Remove selected variables from the DataFrame.
        
        Args:
            df: DataFrame to modify
            variables_to_remove: List of column names to remove
        
        Returns:
            DataFrame with columns removed
        """
        existing_cols = [c for c in variables_to_remove if c in df.columns]
        
        if existing_cols:
            self.logger.info(f"Removing {len(existing_cols)} variables: {existing_cols}")
            return df.drop(columns=existing_cols)
        
        return df


# Global service instance
variable_review_service = VariableReviewService()
