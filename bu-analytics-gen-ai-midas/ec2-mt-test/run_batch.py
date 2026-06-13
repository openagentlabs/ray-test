import argparse
import glob
import os
import time
from datetime import datetime
from tqdm import tqdm

from logging_setup import setup_logging
from pipeline import run_pipeline_for_csv, cleanup_memory
from report import generate_report, generate_summary

def main():
    parser = argparse.ArgumentParser(description="EC2 MT Batch Script")
    parser.add_argument("--data-dir", default=".", help="Directory containing CSV files")
    parser.add_argument("--output-dir", default=None, help="Directory for outputs (default: same as data-dir)")
    parser.add_argument("--glob", default="*.csv", help="Glob pattern for CSV files")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--rfe-locked-count", type=int, default=7, help="Number of locked features for RFE")
    
    args = parser.parse_args()
    
    data_dir = os.path.abspath(args.data_dir)
    output_dir = os.path.abspath(args.output_dir) if args.output_dir else data_dir
    
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_dir = os.path.join(output_dir, "ec2-mt-runs", run_id)
    os.makedirs(run_output_dir, exist_ok=True)
    
    logger = setup_logging(os.path.join(run_output_dir, "batch.log"))
    logger.info(f"Starting batch run {run_id}")
    logger.info(f"Data dir: {data_dir}")
    logger.info(f"Output dir: {run_output_dir}")
    
    csv_files = glob.glob(os.path.join(data_dir, args.glob))
    if not csv_files:
        logger.warning(f"No CSV files found matching {args.glob} in {data_dir}")
        return
        
    logger.info(f"Found {len(csv_files)} CSV files")
    
    all_reports = []
    
    # Progress bar for files
    file_pbar = tqdm(csv_files, desc="Processing files", position=0)
    
    for csv_path in file_pbar:
        csv_stem = os.path.splitext(os.path.basename(csv_path))[0]
        file_pbar.set_description(f"File: {csv_stem}")
        
        csv_output_dir = os.path.join(run_output_dir, csv_stem)
        os.makedirs(csv_output_dir, exist_ok=True)
        
        # Setup per-file logger
        file_logger = setup_logging(os.path.join(csv_output_dir, "run.log"))
        file_logger.info(f"Processing {csv_path}")
        
        dataset_id_ref = None
        try:
            timings, auto_results, dataset_id = run_pipeline_for_csv(
                csv_path=csv_path,
                output_dir=csv_output_dir,
                seed=args.seed,
                rfe_locked_count=args.rfe_locked_count
            )
            dataset_id_ref = dataset_id
            
            if timings and auto_results:
                report = generate_report(csv_output_dir, csv_stem, timings, auto_results)
                all_reports.append(report)
                file_logger.info(f"Successfully processed {csv_path}")
            else:
                file_logger.error(f"Failed to process {csv_path}")
                
        except Exception as e:
            file_logger.exception(f"Unhandled exception processing {csv_path}: {e}")
        finally:
            if dataset_id_ref:
                cleanup_memory(dataset_id_ref)
                
            # Re-setup batch logger
            logger = setup_logging(os.path.join(run_output_dir, "batch.log"))
            
    generate_summary(run_output_dir, all_reports)
    logger.info(f"Batch run {run_id} completed. Summary written to {run_output_dir}/summary.json")

if __name__ == "__main__":
    main()
