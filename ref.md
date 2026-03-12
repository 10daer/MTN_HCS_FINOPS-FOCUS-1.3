okay let implement the tag endpoints

here are all the api url,

1. This API is used to query the list of resources bound to a tag.
   curl -i -k -H "Content-Type: application/json" -H "Accept:application/json"
   -H "x-auth-token:XXXXX" -X POST
   "https://accessip:port/rest/tag/v3.0/tags/resources/action" -d '{ "tags":
   [{ "key": "xxxx", "value": "XXXX"}],"tags_any": [{ "key": "XXXX","value":
   "XXXX" }], "region_id": "XXXX","resource_id": "XXXX","resource_name":
   "XXXX","project_id": "XXXX","resource_type": "XXXX","limit": "10","start":
   "0","action": "count" }'
   Sample request
   POST /rest/tag/v3.0/tags/resources/action HTTP/1.1
   Content-Type: application/json
   Accept: application/json
   x-auth-token: xxx
   {
   "tags":
   [{
   "key": "xxx",
   "value": "xxx"
   }],
   "tags_any":
   [{
   "key": "xxx",
   "value": "xxx"
   }],
   "project_id": "xxxx",
   "region_id": "xxx",
   "cloud_infra_id": "xxxx",
   "resource_id": "xxx",
   "resource_name": "xxx",
   "resource_type": "xxx",
   "limit": "xxx",
   "start": "xxx",
   "action": "filter|count|accurate_query"
   }
   Sample response
   HTTP/1.1 200 OK
   Content-Type: application/json;charset=UTF8
   {
   "total": 0,
   "resources": [{
   "region_id": "xxxx",
   "project_id": "xxxx",
   "cloud_infra_id": "xxxx",
   "resource_id": "xxxx",
   "resource_name": "xxxx",
   "resource_type": "xxxx",
   "tags":
   [{
   "key": "xxx",
   "value": "xxx",
   "operate_time": "yyyy-MM-dd HH:mm:ss"
   }]
   }]
   }

2)Query predefined tags (new).
curl -i -k -H "Content-Type: application/json" -H "Accept:application/json"
-H "x-auth-token:" -X GET
"https://accessip:port/v1.0/predefine_tags?key=tagkey"
Sample request
GET
/v1.0/predefine_tags?key=ENV&value=DEV&limit=10&marker=9&order_field=key&
order_method=asc HTTP/1.1
Content-Type: application/json
Accept: application/json
x-auth-token: XXX
Sample response
HTTP/1.1 200 OK
{
"marker": "12",
"total_count": 13,
"tags": [
{
"key": "ENV1",
"value": "DEV1",
"update_time": "2017-04-12T14:22:34Z"
},
{
"key": "ENV2",
"value": "DEV2",
"update_time": "2017-04-12T14:22:34Z"
}
]
}

3. Create or delete tags in batches
   T /rest/tag/v3.0/tags HTTP/1.1
   Content-Type: application/json;charset=UTF8
   Accept: application/json
   x-auth-token: xxx
   {
   "action": "create",
   "tags": [
   {
   "key": "key1",
   "value": "value1"
   },
   {
   "key": "key1",
   "value": "value2"
   }
   ]
   }
   Response parameters
   l Sample response
   HTTP/1.1 204 OK

4) Verify the permissions on resources before they are associated to or disassociated from tags.
   Sample request
   POST /tag/v3.0/tags/authen HTTP/1.1
   Content-Type: application/json
   Accept: application/json
   x-auth-token: xxx
   {
   "user_id": "XXX",
   "resource_id": "xxx",
   "cloud_infra_id": "xxx",
   "project_id": "xxxx",
   "region_id": "xxx",
   "bind_tags": [{
   "key": "xxx",
   "value": "xxx"
   }],
   "unbind_tags": [{
   "key": "xxx",
   "value": "xxx"
   }]
   }

   Sample response
   HTTP/1.1 200 OK
