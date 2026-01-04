"""Check job status and worker tasks"""
import asyncio
import sys
import os

script_dir = os.path.dirname(__file__)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from services.ai_dictionary_generator import ai_dictionary_generator

async def check_job():
    job_id = "dict_1_27597e45"
    
    print(f"Checking job: {job_id}")
    print("=" * 80)
    
    # Check if job is in memory
    if job_id in ai_dictionary_generator._jobs:
        job = ai_dictionary_generator._jobs[job_id]
        print(f"Job found in memory:")
        print(f"  Status: {job.status.value}")
        print(f"  Total tables: {len(job.table_tasks)}")
        print(f"  Current table: {job.current_table}")
        print(f"  Workers: {len(ai_dictionary_generator._workers)}")
        print(f"  Queue size: {ai_dictionary_generator._queue.qsize()}")
        
        print("\nTable tasks:")
        for table_key, task in job.table_tasks.items():
            print(f"  {table_key}: {task.status.value} (progress: {task.progress}%)")
    else:
        print("Job not found in memory, loading from database...")
        await ai_dictionary_generator._load_job_from_db(job_id)
        
        if job_id in ai_dictionary_generator._jobs:
            job = ai_dictionary_generator._jobs[job_id]
            print(f"Job loaded from database:")
            print(f"  Status: {job.status.value}")
            print(f"  Total tables: {len(job.table_tasks)}")
            print(f"  Current table: {job.current_table}")
            
            print("\nTable tasks:")
            for table_key, task in job.table_tasks.items():
                print(f"  {table_key}: {task.status.value} (progress: {task.progress}%)")
        else:
            print("Job not found in database either")
    
    print(f"\nWorkers status: {len(ai_dictionary_generator._workers)} workers")
    print(f"Queue size: {ai_dictionary_generator._queue.qsize()}")
    
    # Try to start the job if it's waiting
    if job_id in ai_dictionary_generator._jobs:
        job = ai_dictionary_generator._jobs[job_id]
        if job.status.value == "waiting":
            print("\nJob is waiting, attempting to start...")
            result = await ai_dictionary_generator.start_job(job_id)
            print(f"Start result: {result}")
            print(f"Workers after start: {len(ai_dictionary_generator._workers)}")
            print(f"Queue size after start: {ai_dictionary_generator._queue.qsize()}")

if __name__ == "__main__":
    asyncio.run(check_job())




