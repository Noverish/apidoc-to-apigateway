import boto3
from pprint import pprint
import json
import re
import config

client = boto3.Session(profile_name=config.PROFILE_NAME).client('apigateway')
lambda_client = boto3.Session(profile_name=config.PROFILE_NAME).client('lambda')
rest_api_id = list(filter(lambda api: api['name'] == config.REST_API_NAME, client.get_rest_apis()['items']))[0]['id']
resources = client.get_resources(restApiId=rest_api_id, limit=500)['items']

f = open('template.txt')
template = f.read()
f.close()

for method in json.load(open(config.JSON_PATH)):
    title = method['title']
    function_name = method['name']
    httpMethod = method['type'].upper()
    path = method['url']
    statusCodes = [int(res['content'][9:12]) for res in method['success']['examples']]
    print('Processing', httpMethod, path, statusCodes)

    statusCodes += config.DEFAULT_STATUS_CODE

    parent_path = ""
    now_path = ""
    for part in path[1:].split('/'):
        parent_path = now_path
        now_path = parent_path + "/" + part

        if now_path not in [r['path'] for r in resources]:
            parent_resource_id = [r['id'] for r in resources if r['path'] == (parent_path if len(parent_path) != 0 else "/")][0]

            resource = client.create_resource(restApiId=rest_api_id, parentId=parent_resource_id, pathPart=part)

            resources.append({
                'id': resource['id'],
                'parentId': resource['parentId'],
                'path': resource['path'],
                'pathPart': resource['pathPart']
            })

            print('  Created Resource :', now_path)

    resourceId = [r['id'] for r in resources if r['path'] == path][0]

# Create method if not exists
    try:
        aws_method = client.get_method(
            restApiId=rest_api_id,
            resourceId=resourceId,
            httpMethod=httpMethod
        )
    except:
        aws_method = client.put_method(
            restApiId=rest_api_id,
            resourceId=resourceId,
            httpMethod=httpMethod,
            authorizationType='NONE'
        )

        print('  Created Method :', httpMethod)

# Connect lambda function to method
    function_arn = lambda_client.get_function(FunctionName=function_name)['Configuration']['FunctionArn']
    uri = 'arn:aws:apigateway:' + config.REGION + ':lambda:path/2015-03-31/functions/' + function_arn + '/invocations'

    try:
        aws_integration = client.get_integration(restApiId=rest_api_id, resourceId=resourceId, httpMethod=httpMethod)
    except:
        aws_integration = client.put_integration(
            restApiId=rest_api_id,
            resourceId=resourceId,
            httpMethod=httpMethod,
            type='AWS',
            integrationHttpMethod='POST',
            uri=uri,
            requestTemplates={
                'application/json': template
            },
            passthroughBehavior='WHEN_NO_TEMPLATES',
            contentHandling='CONVERT_TO_TEXT'
        )

        print('  Created Integration :', function_name)

# Added permission to lambda function
    sourceArn = 'arn:aws:execute-api:' + config.REGION + ':' + config.AWS_ACCOUNT_ID + ':' + rest_api_id + '/*/' + httpMethod + re.sub(r'[{][^}]*?[}]', '*', path)

    has_permission = False
    try:
        policy = eval(lambda_client.get_policy(FunctionName=function_name)['Policy'])
        statementId = policy['Id']

        for statement in policy['Statement']:
            aws_source_arn = statement['Condition']['ArnLike']['AWS:SourceArn']

            if aws_source_arn == sourceArn:
                has_permission = True
    except:
        pass

    if not has_permission:
        response = lambda_client.add_permission(
            FunctionName=function_name,
            StatementId='custom_statement_id_' + title,
            Action='lambda:InvokeFunction',
            Principal='apigateway.amazonaws.com',
            SourceArn=sourceArn
        )

        print('  Added Permission to Lambda Function :', function_name)

# Process status code and integration response
    for statusCode in [str(code) for code in statusCodes]:

        # Added status code
        try:
            aws_method_res = client.get_method_response(
                restApiId=rest_api_id,
                resourceId=resourceId,
                httpMethod=httpMethod,
                statusCode=statusCode
            )
        except:
            aws_method_res = client.put_method_response(
                restApiId=rest_api_id,
                resourceId=resourceId,
                httpMethod=httpMethod,
                statusCode=statusCode
            )

            print('  Created Method Response :', statusCode)

        # Added integration response
        try:
            aws_integration_res = client.get_integration_response(
                restApiId=rest_api_id,
                resourceId=resourceId,
                httpMethod=httpMethod,
                statusCode=statusCode
            )

            if config.SELECTION_PATTERN[statusCode] != aws_integration_res['selectionPattern']:
                response = client.delete_integration_response(
                    restApiId=rest_api_id,
                    resourceId=resourceId,
                    httpMethod=httpMethod,
                    statusCode=statusCode
                )

                print('  Deleted Integration Response :', statusCode)

                aws_integration_res = None
        except:
            aws_integration_res = None

        if aws_integration_res is None:
            aws_integration_res = client.put_integration_response(
                restApiId=rest_api_id,
                resourceId=resourceId,
                httpMethod=httpMethod,
                statusCode=statusCode,
                selectionPattern=config.SELECTION_PATTERN[statusCode]
            )

            print('  Created Integration Response :', statusCode)

response = client.create_deployment(
    restApiId=rest_api_id,
    stageName=config.STAGE_NAME
)

print('done!')
