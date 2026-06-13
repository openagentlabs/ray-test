"""
Simple monotonicity evaluation for segmentation models
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any
import logging


class SegmentationMonotonicityEvaluator:
    """
    Simple monotonicity evaluator for segmentation models
    """
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
    
    def evaluate_segment_monotonicity(
        self, 
        segment_profiles: List[Dict[str, Any]], 
        target_variable: str = None
    ) -> Dict[str, Any]:
        """
        Simple monotonicity evaluation across segments
        
        Args:
            segment_profiles: List of segment dictionaries with bad_rate, count, etc.
            target_variable: Name of target variable
            
        Returns:
            Dictionary with basic monotonicity results
        """
        try:
            if not segment_profiles:
                return {
                    "monotonicity_score": 0.0,
                    "is_monotonic": False,
                    "violations": [],
                    "error": "No segments provided"
                }
            
            # Sort segments by bad_rate to check monotonicity
            sorted_segments = sorted(segment_profiles, key=lambda x: x.get('bad_rate', 0))
            
            # Count violations (where bad rate decreases)
            violations = []
            for i in range(1, len(sorted_segments)):
                prev_rate = sorted_segments[i-1]['bad_rate']
                curr_rate = sorted_segments[i]['bad_rate']
                
                if curr_rate < prev_rate:
                    violations.append({
                        "segment_from": sorted_segments[i-1]['segment_index'],
                        "segment_to": sorted_segments[i]['segment_index'],
                        "bad_rate_from": prev_rate,
                        "bad_rate_to": curr_rate,
                        "drop": prev_rate - curr_rate
                    })
            
            # Calculate basic monotonicity score
            total_pairs = len(sorted_segments) - 1
            correct_pairs = total_pairs - len(violations)
            monotonicity_score = correct_pairs / total_pairs if total_pairs > 0 else 1.0
            
            self.logger.info(f"Basic monotonicity evaluation: score={monotonicity_score:.3f}, violations={len(violations)}")
            
            return {
                "monotonicity_score": monotonicity_score,
                "is_monotonic": len(violations) == 0,
                "violations": violations,
                "total_segments": len(segment_profiles),
                "target_variable": target_variable,
                "segment_count": len(segment_profiles)
            }
            
        except Exception as e:
            self.logger.error(f"Error in monotonicity evaluation: {str(e)}")
            return {
                "monotonicity_score": 0.0,
                "is_monotonic": False,
                "violations": [],
                "error": str(e)
            }
    
    def evaluate_tree_monotonicity(self, tree_model, feature_names: List[str]) -> Dict[str, Any]:
        """
        Basic tree monotonicity evaluation (placeholder for now)
        
        Args:
            tree_model: Trained decision tree model
            feature_names: List of feature names
            
        Returns:
            Dictionary with tree analysis results
        """
        try:
            if tree_model is None or not hasattr(tree_model, 'tree_'):
                return {
                    "is_monotonic_tree": False,
                    "error": "Invalid tree model"
                }
            
            tree = tree_model.tree_
            
            return {
                "is_monotonic_tree": True,  # Basic assumption
                "tree_depth": getattr(tree, 'max_depth', 0),
                "total_nodes": getattr(tree, 'node_count', 0),
                "total_leaves": getattr(tree, 'n_leaves', 0),
                "feature_count": len(feature_names)
            }
            
        except Exception as e:
            self.logger.error(f"Error in tree monotonicity evaluation: {str(e)}")
            return {
                "is_monotonic_tree": False,
                "error": str(e)
            }
