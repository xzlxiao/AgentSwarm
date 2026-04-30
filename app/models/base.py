from pydantic import BaseModel, ConfigDict


class MongoModel(BaseModel):
    """MongoDB 文档 Pydantic 基类。"""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    id: str | None = None


def mongo_doc_to_model(doc: dict[str, object], model_class: type[MongoModel]) -> MongoModel:
    """将 MongoDB 原始文档转换为 Pydantic Model。"""
    copied = doc.copy()
    _id = copied.get("_id")
    if _id is not None:
        copied["id"] = str(_id)
    copied.pop("_id", None)
    return model_class.model_validate(copied)


def model_to_mongo_doc(model: MongoModel) -> dict[str, object]:
    """将 Pydantic Model 转为 MongoDB 写入用的 dict。排除 id 和 None 值。"""
    return model.model_dump(exclude_none=True, exclude={"id"})
