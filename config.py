PROFILE_NAME = "zium"
AWS_ACCOUNT_ID = "464151917901"
REGION = "ap-northeast-2"
REST_API_NAME = "KUSulang_v2"
STAGE_NAME = "develop"
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