from pydantic import BaseModel, Field, validator


class ImportanceRatingResponse(BaseModel):
    rating: int = Field(description="重要度 1 ~ 10 の整数値")

    @validator("rating")
    def validate_cron_jobs(cls, rating):
        if rating < 1 or rating > 10:
            raise ValueError(f"rating must be between 1 and 10. Got: {rating}")

        return rating
