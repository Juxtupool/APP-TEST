/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const collection = new Collection({
    "id": "52p56pklkn98iqu",
    "created": "2026-07-18 19:37:53.777Z",
    "updated": "2026-07-18 19:37:53.777Z",
    "name": "macros",
    "type": "base",
    "system": false,
    "schema": [
      {
        "system": false,
        "id": "w4sdo8xx",
        "name": "name",
        "type": "text",
        "required": true,
        "presentable": false,
        "unique": false,
        "options": {
          "min": null,
          "max": null,
          "pattern": ""
        }
      },
      {
        "system": false,
        "id": "50b86twm",
        "name": "author",
        "type": "text",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "min": null,
          "max": null,
          "pattern": ""
        }
      },
      {
        "system": false,
        "id": "pxbnygfs",
        "name": "description",
        "type": "text",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "min": null,
          "max": null,
          "pattern": ""
        }
      },
      {
        "system": false,
        "id": "jimh4avh",
        "name": "category",
        "type": "select",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "maxSelect": 1,
          "values": [
            "productivity",
            "creative",
            "gaming",
            "entertainment",
            "office",
            "other"
          ]
        }
      },
      {
        "system": false,
        "id": "uezem8ve",
        "name": "tags",
        "type": "json",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "maxSize": 5242880
        }
      },
      {
        "system": false,
        "id": "l5ddyghe",
        "name": "type",
        "type": "select",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "maxSelect": 1,
          "values": [
            "macro",
            "profile"
          ]
        }
      },
      {
        "system": false,
        "id": "iurvm8zp",
        "name": "macro_data",
        "type": "json",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "maxSize": 5242880
        }
      },
      {
        "system": false,
        "id": "pqde43fo",
        "name": "profile_data",
        "type": "json",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "maxSize": 5242880
        }
      },
      {
        "system": false,
        "id": "fjmtd8kq",
        "name": "likes",
        "type": "number",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "min": 0,
          "max": null,
          "noDecimal": true
        }
      },
      {
        "system": false,
        "id": "zkkor7cw",
        "name": "downloads",
        "type": "number",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "min": 0,
          "max": null,
          "noDecimal": true
        }
      },
      {
        "system": false,
        "id": "7bfsz7kx",
        "name": "approved",
        "type": "bool",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {}
      }
    ],
    "indexes": [],
    "listRule": "approved = true",
    "viewRule": "approved = true",
    "createRule": "",
    "updateRule": "@request.data.name:isset = false && @request.data.macro_data:isset = false && @request.data.profile_data:isset = false && @request.data.author:isset = false && @request.data.description:isset = false && @request.data.category:isset = false && @request.data.tags:isset = false && @request.data.approved:isset = false",
    "deleteRule": null,
    "options": {}
  });

  return Dao(db).saveCollection(collection);
}, (db) => {
  const dao = new Dao(db);
  const collection = dao.findCollectionByNameOrId("52p56pklkn98iqu");

  return dao.deleteCollection(collection);
})
