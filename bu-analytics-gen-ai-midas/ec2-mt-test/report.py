import json
import os

def generate_report(output_dir, csv_stem, timings, auto_training_results):
    report_data = {
        "csv_file": f"{csv_stem}.csv",
        "timings": timings,
        "models": []
    }
    
    if auto_training_results and "results" in auto_training_results:
        for res in auto_training_results["results"]:
            if "error" in res:
                report_data["models"].append({
                    "algorithm": res.get("algorithm"),
                    "status": "failed",
                    "error": res.get("error")
                })
                continue
                
            metrics = res.get("metrics", {})
            model_info = {
                "algorithm": res.get("algorithm"),
                "model_id": res.get("model_id"),
                "status": "success",
                "training_time_seconds": res.get("training_time_seconds", 0),
            }
            
            # Add key metrics based on problem type
            if "test_auc" in metrics or "auc" in metrics:
                model_info["auc"] = metrics.get("test_auc", metrics.get("auc"))
                model_info["f1"] = metrics.get("test_f1", metrics.get("f1"))
                model_info["accuracy"] = metrics.get("test_accuracy", metrics.get("accuracy"))
            else:
                model_info["r2"] = metrics.get("test_r2", metrics.get("r2"))
                model_info["rmse"] = metrics.get("test_rmse", metrics.get("rmse"))
                
            report_data["models"].append(model_info)
            
    # Write JSON
    json_path = os.path.join(output_dir, "report.json")
    with open(json_path, "w") as f:
        json.dump(report_data, f, indent=2)
        
    # Write Markdown
    md_path = os.path.join(output_dir, "report.md")
    with open(md_path, "w") as f:
        f.write(f"# Training Report: {csv_stem}.csv\n\n")
        f.write("## Phase Timings\n\n")
        f.write("| Phase | Seconds |\n")
        f.write("|-------|---------|\n")
        for phase, t in timings.items():
            f.write(f"| {phase} | {t:.2f} |\n")
            
        f.write("\n## Models\n\n")
        if not report_data["models"]:
            f.write("No models trained successfully.\n")
        else:
            # Check if classification or regression
            is_classification = any("auc" in m for m in report_data["models"])
            
            if is_classification:
                f.write("| Algorithm | Model ID | Time (s) | AUC | F1 | Accuracy | Status |\n")
                f.write("|-----------|----------|----------|-----|----|----------|--------|\n")
                for m in report_data["models"]:
                    if m["status"] == "failed":
                        f.write(f"| {m.get('algorithm')} | - | - | - | - | - | Failed: {m.get('error')} |\n")
                    else:
                        f.write(f"| {m.get('algorithm')} | {m.get('model_id')} | {m.get('training_time_seconds', 0):.1f} | {m.get('auc', 0):.4f} | {m.get('f1', 0):.4f} | {m.get('accuracy', 0):.4f} | Success |\n")
            else:
                f.write("| Algorithm | Model ID | Time (s) | R2 | RMSE | Status |\n")
                f.write("|-----------|----------|----------|----|------|--------|\n")
                for m in report_data["models"]:
                    if m["status"] == "failed":
                        f.write(f"| {m.get('algorithm')} | - | - | - | - | Failed: {m.get('error')} |\n")
                    else:
                        f.write(f"| {m.get('algorithm')} | {m.get('model_id')} | {m.get('training_time_seconds', 0):.1f} | {m.get('r2', 0):.4f} | {m.get('rmse', 0):.4f} | Success |\n")
                        
    return report_data

def generate_summary(output_dir, reports):
    summary_path = os.path.join(output_dir, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(reports, f, indent=2)
