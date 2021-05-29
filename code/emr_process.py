import argparse
import logging
import time
import boto3
from botocore.exceptions import ClientError
import emr
import iam
import ec2
import s3
import poller

logger = logging.getLogger(__name__)


def create_cluster(cfile, prefix = 'cluster_default'):

    if prefix.find("cluster") < 0:
        print("The cluster name cannot contain the word 'cluster'")
        return 

    folders = ['scripts', 'logs', 'steps', 'output', 'input']

    prefix = f'{prefix}-{time.time_ns()}'

    bucket = s3.create_bucket(prefix, folders, logger)

    job_flow_role, service_role = iam.create_roles(
        f'{prefix}-ec2-role', 
        f'{prefix}-service-role')

    security_groups = ec2.create_security_groups(prefix)

    print("Wait for 10 seconds to give roles and profiles time to propagate...")

    time.sleep(10)

    max_tries = 5
    while True:
        try:
            cluster_id = emr.run_job_flow(
                f'cluster-{prefix}',
                f's3://{prefix}/logs',
                True, 
                ['Hadoop', 'Hive', 'Spark'], 
                job_flow_role, 
                service_role,
                security_groups, logger)
            print(f"Running job flow for cluster {cluster_id}...")
            break
        except ClientError as error:
            max_tries -= 1
            if max_tries > 0 and \
                    error.response['Error']['Code'] == 'ValidationException':
                print("Instance profile is not ready, let's give it more time...")
                time.sleep(10)
            else:
                raise

def list_clusters():
    emr.list_clusters(logger)

def terminate_cluster(cluster_id, remove_all = False):
    
    cluster_name = emr.describe_cluster(cluster_id, logger)['Name']
    prefix_name = cluster_name.replace("cluster-", '')
    job_flow_role = f'{prefix_name}-ec2-role'
    service_role =  f'{prefix_name}-service-role'

    emr.terminate_cluster(cluster_id, logger)

    if remove_all:
        remove_everything = input(
        f"Do you want to delete the security roles, groups, and bucket (y/n)? ")

        if remove_everything.lower() == 'y':
                iam.delete_roles([job_flow_role, service_role])
                ec2.delete_security_groups(security_groups, logger)
                s3.delete_bucket(prefix_name)
        else:
            print(f"Remember that objects kept in Amazon can incur charges")
    else:
        remove_sr = input(
        f"Do you want to delete the security roles (y/n)? ")

        if remove_sr.lower() == 'y':
            iam.delete_roles([job_flow_role, service_role], logger)
        else:
            print(
            f"Remember that objects kept in Amazon can incur charges")

        remove_sg = input(
        f"Do you want to delete the security groups (y/n)? ")

        if remove_sg.lower() == 'y':
            ec2.delete_security_groups(security_groups, prefix_name, logger)
        else:
            print(
            f"Remember that objects kept in Amazon can incur charges")

        remove_s3 = input(
        f"Do you want to delete the S3 bucket (y/n)? ")

        if remove_s3.lower() == 'y':
            s3.delete_bucket(prefix_name)
        else:
            print(
            f"Remember that objects kept in Amazon S3 bucket can incur charges")



if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('-a','--Action', type=str, help = "Type of actions", metavar = '', choices=['create_cluster', 
                                                                                      'list_clusters',
                                                                                      'terminate_cluster',
                                                                                      'add_steps',
                                                                                      'delete_steps',
                                                                                      'execute_steps'])


    # Create cluster
    parser.add_argument('-c','--cname', type=str, help = "Name Cluster")
    parser.add_argument('-cfg','--cfile', type=str, help = "File with the fonfiguration of the emr cluster")


    # Terminate cluster
    parser.add_argument('-idc','--cluster_id', type=str, help = "Id of the cluster")

    # add steps to the cluster
    parser.add_argument('-steps','--sfile', type=str, help = "Add steps from json file")

    # execute steps in clusters
    parser.add_argument('-execute_steps','--Execute steps in cluster', type=str, help = "execute steps involved to the clusters")    


    args = parser.parse_args()

    if args.Action == 'create_cluster':
        create_cluster(args.cfile, args.cname)
    elif args.Action == 'list_clusters':
        list_clusters()
    elif args.Action == 'terminate_cluster':
        terminate_cluster(args.cluster_id)
    elif args.Action == 'add_steps':
        add_steps(args.sfile, args.cluster_id)
    elif args.Action == 'delete_steps':
        delete_steps(args.cluster_id)        
    elif args.Action == 'execute_steps':
        execute_steps(args.cluster_id)
    else:
        print("Action is invalid")