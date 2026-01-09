from airflow.operators.python import PythonOperator
from airflow import DAG
from utils.job_scrapper.job_link_scrapper import * 
from utils.job_scrapper.job_info import *
from airflow.utils.task_group import TaskGroup
from airflow.operators.empty import EmptyOperator
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from dotenv import load_dotenv
load_dotenv()

with DAG(
    dag_id="job_scrapper",
    description="dag for scraping job links and job deatils",
    start_date=datetime(2025, 12, 17),
    schedule_interval="*/15 * * * *",
    catchup=False

) as dag :

    roles=["data engineer", "data analyst"]
    # roles=["data engineer"]

    scrape_job_links = PythonOperator (
        task_id = "scrape_job_links",
        python_callable= scrape_linkedin_jobs,
        params={
            "job_roles" : roles,
            "options" :{
                "time_posted": 1200,  
                "location": "United States"
             }
        }
    )


    process_tasks = []
    with TaskGroup(group_id='process_jobs_by_role') as process_group:
        for role in roles:
            safe_role_name = role.replace(" ", "_").lower()
            
            # Process and save job information in a single task
            process_task = PythonOperator(
                task_id=f'process_{safe_role_name}_jobs',
                python_callable=get_job_information,
                provide_context=True,
                op_kwargs={'job_role': role}  # Pass the job role directly
            )
            
            process_tasks.append(process_task)

    end = EmptyOperator(
        task_id='end',
    )

    scrape_job_links >> process_group >> end