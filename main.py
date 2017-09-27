import boto3
from pprint import pprint
import json
import re

AWS_ACCOUNT_ID = "464151917901"
REGION = "ap-northeast-2"
REST_API_NAME = "KUSulang_v2"
JSON_PATH = "../KUSulang-lambda/doc/api_data.json"
DEFAULT_STATUS_CODE = [400, 401, 403, 404, 500]
SELECTION_PATTERN = {
    '200': '',
    '204': '',
    '400': '\[400 Bad Request.*',
    '401': '\[401 Unauthorized.*',
    '403': '\[403 Forbidden.*',
    '404': '\[404 Not Found.*',
    '500': '.+'
}

client = boto3.Session(profile_name='zium').client('apigateway')
lambda_client = boto3.Session(profile_name='zium').client('lambda')
rest_api_id = list(filter(lambda api: api['name'] == REST_API_NAME, client.get_rest_apis()['items']))[0]['id']
resources = client.get_resources(restApiId=rest_api_id, limit=500)['items']

f = open('template.txt')
template = f.read()
f.close()

for method in json.load(open(JSON_PATH)):
    httpMethod = method['type'].upper()
    path = method['url']
    statusCodes = [int(res['content'][9:12]) for res in method['success']['examples']]
    print('Processing', httpMethod, path, statusCodes)

    statusCodes += DEFAULT_STATUS_CODE

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
    function_name = REST_API_NAME + "_" + method['title']
    origin_function_name = function_name
    function_name = function_name.replace("other_", "")
    function_arn = lambda_client.get_function(FunctionName=function_name)['Configuration']['FunctionArn']
    uri = 'arn:aws:apigateway:' + REGION + ':lambda:path/2015-03-31/functions/' + function_arn + '/invocations'

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

        print('  Created Integration :', method['title'])

# Added permission to lambda function
    sourceArn = 'arn:aws:execute-api:' + REGION + ':' + AWS_ACCOUNT_ID + ':' + rest_api_id + '/*/' + httpMethod + re.sub(r'[{][^}]*?[}]', '*', path)

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
            StatementId='custom_statement_id_' + origin_function_name,
            Action='lambda:InvokeFunction',
            Principal='apigateway.amazonaws.com',
            SourceArn=sourceArn
        )

        print('  Added Permission to Lambda Function :', method['title'])

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

            if SELECTION_PATTERN[statusCode] != aws_integration_res['selectionPattern']:
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
                selectionPattern=SELECTION_PATTERN[statusCode]
            )

            print('  Created Integration Response :', statusCode)

    # resource = None
    #
    # try:
    #     resource = [r for r in resources if r['path'] == path][0]
    # except IndexError:
    #     for i, part in :
    #         parent_path =
    #         print(parent_path)
    #         print("asdf")

        # resource = client.create_resource(restApiId=rest_api_id, parentId='string', pathPart='string')

#
#
#
#
# for resource in resources:
#     if 'resourceMethods' not in resource:
#         continue
#
#     for httpMethod in resource['resourceMethods'].keys():
#
#         resourceId = resource['id']
#         path = resource['path'].replace('{', ':').replace('}', '')
#
#         if path == '/':
#             continue
#
#         print(path)
#         print(methods[httpMethod + " " + path])
#
#         method = client.get_method(restApiId=rest_api_id, resourceId=resourceId, httpMethod=httpMethod)
#
#         methodResponses = method['methodResponses']
#         methodIntegration = method['methodIntegration']
#         integrationResponses = methodIntegration['integrationResponses']

        # tmp = client.put_method_response(
        #     restApiId=rest_api_id,
        #     resourceId=resourceId,
        #     httpMethod=httpMethod,
        #     statusCode='string',
        #     responseParameters={
        #         'string': True | False
        #     },
        #     responseModels={
        #         'string': 'string'
        #     }
        # )
