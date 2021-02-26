import json
import os


def type_rad2openapi(rad_type):
    rad_type = rad_type.lower()
    if rad_type in ["int", "integer"]:
        return "integer", "int32"

    if rad_type in ["long"]:
        return "integer", "int64"

    if rad_type in ["bool", "boolean"]:
        return "boolean", None

    if rad_type in ["float", "double"]:
        return "number", None

    if rad_type in ["string", "str", "text"]:
        return "string", None

    if rad_type in ["date"]:
        return "string", "date"

    if rad_type in ["list", "array"] or "list<" in rad_type:
        return "array", None

    print(rad_type)
    return "object", None


def convert_schema_name(name):
    return name.replace(' ', '-').replace('[', '').replace(']', '')


def convert(restapidoc_filepath, openapi_filepath):
    print(os.path.exists(restapidoc_filepath))
    with open(restapidoc_filepath, 'r') as r:
        rad = json.load(r)

    openapi = {
        "openapi": "3.0.1",
        "info": {
            "title": "Cytomine API",
            "version": "1.0.0"
        }
    }

    schemas = {}
    for rad_object in rad['objects']:
        props = {}
        requireds = []
        for rad_field in rad_object["fields"]:
            _type, _format = type_rad2openapi(rad_field["type"])
            if _type == "object":
                print(rad_object['name'])
                print(rad_field['name'])
                print()
            schema = {
                "type": _type,
                "description": rad_field["description"],
            }
            if _format:
                schema["format"] = _format
            if rad_field["defaultValue"] is not None:
                schema["default"] = rad_field["defaultValue"]
            if _type == "array":
                subtype = "string"
                subformat = None
                if "<" in rad_field["type"] and ">" in rad_field["type"]:
                    s = rad_field["type"]
                    subtype, subformat = type_rad2openapi(s[s.find("<")+1:s.rfind(">")])
                schema["items"] = {"type": subtype}
                if subformat:
                    schema["items"]["format"] = subformat
            if rad_field["useForCreation"] and not rad_field["presentInResponse"]:
                schema["writeOnly"] = True
            if not rad_field["useForCreation"] and rad_field["presentInResponse"]:
                schema["readOnly"] = True

            props[rad_field["name"]] = schema
            if rad_field["mandatory"]:
                requireds.append(rad_field["name"])



        schema = {
            "description": rad_object["description"],
            "type": "object",
            "properties": props,
        }

        if len(requireds) > 0:
            schema["required"] = requireds

        schemas[convert_schema_name(rad_object["name"])] = schema

    tags = []
    paths = {}

    for rad_api in rad['apis']:
        tags.append({
            "name": rad_api['name'],
            "description": rad_api['description']
        })

        for rad_method in rad_api["methods"]:

            if rad_method["path"] not in paths.keys():
                paths[rad_method["path"]] = {}

            path = paths[rad_method["path"]]

            if rad_method["verb"] in path.keys():
                print("{} already in path {}".format(rad_method["verb"], rad_method["path"]))
                continue

            parameters = []
            for rad_param in rad_method["pathparameters"]:
                _type, _format = type_rad2openapi(rad_param["type"])
                schema = {"type": _type}
                if _format:
                    schema["format"] = _format

                if _type == "array":
                    subtype = "string"
                    subformat = None
                    if "<" in rad_param["type"] and ">" in rad_param["type"]:
                        s = rad_param["type"]
                        subtype, subformat = type_rad2openapi(s[s.find("<") + 1:s.rfind(">")])
                    schema["items"] = {"type": subtype}
                    if subformat:
                        schema["items"]["format"] = subformat

                parameters.append({
                    "name": rad_param["name"],
                    "in": "path",
                    "description": rad_param["description"],
                    "required": True if rad_param["required"] == "true" else False,
                    "schema": schema
                })

            has_max = False
            has_offset = False
            for rad_param in rad_method["queryparameters"]:
                _type, _format = type_rad2openapi(rad_param["type"])
                schema = {"type": _type}
                if _format:
                    schema["format"] = _format

                if _type == "array":
                    subtype = "string"
                    subformat = None
                    if "<" in rad_param["type"] and ">" in rad_param["type"]:
                        s = rad_param["type"]
                        subtype, subformat = type_rad2openapi(s[s.find("<") + 1:s.rfind(">")])
                    schema["items"] = {"type": subtype}
                    if subformat:
                        schema["items"]["format"] = subformat

                parameters.append({
                    "name": rad_param["name"],
                    "in": "query",
                    "description": rad_param["description"],
                    "required": True if rad_param["required"] == "true" else False,
                    "schema": schema
                })

                if rad_param["name"] == "max":
                    has_max = True

                if rad_param["name"] == "offset":
                    has_offset = True

            responses = {}
            for rad_resp in rad_method["apierrors"]:
                responses[rad_resp["code"]] = {
                    "description": rad_resp["description"]
                }

            if rad_method["response"]["object"]:
                schema_name = convert_schema_name(rad_method["response"]["object"])
                if schema_name in schemas.keys():
                    if has_max and has_offset:
                        schema = {
                            "type": "array",
                            "items": {
                                "$ref": '#/components/schemas/{}'.format(schema_name)
                            }
                        }
                    else:
                        schema = {"$ref": '#/components/schemas/{}'.format(schema_name)}
                    response = {
                        "content": {
                            "application/json": {
                                "schema": schema
                            }
                        },
                        "description": ""
                    }
                else:
                    response = {
                        "description": rad_method["response"]["object"]
                    }
                responses[200] = response

            operation = {
                "tags": [rad_api["name"]],
                "description": rad_method.get("description", None),
                "parameters": parameters,
                "responses": responses
            }

            if rad_method["verb"].lower() in ["post", "put"]:
                schema_name = convert_schema_name(rad_method["response"]["object"])
                if schema_name in schemas.keys():
                    operation["requestBody"] = {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": '#/components/schemas/{}'.format(schema_name)
                                }
                            }
                        }
                    }

            paths[rad_method["path"]][rad_method["verb"].lower()] = operation

    openapi["tags"] = tags
    openapi["paths"] = paths
    openapi["components"] = {
        "schemas": schemas
    }

    with open(openapi_filepath, 'w') as f:
        json.dump(openapi, f)


if __name__ == '__main__':
    restapidoc = "restapidoc.json"
    openapi = "openapi.json"
    convert(restapidoc, openapi)