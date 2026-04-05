from __future__ import annotations

import sys


if sys.version_info < (3, 14):
    from uagents import Model as AgentModel

    class ReviewRequestEnvelope(AgentModel):
        correlation_id: str
        issue_json: str
        round_number: int = 1
        rebuttal_request: str | None = None


    class AudienceReviewEnvelope(AgentModel):
        correlation_id: str
        review_json: str


    class BossReviewRequestEnvelope(AgentModel):
        correlation_id: str
        issue_json: str
        reviews_json: str


    class BossReviewEnvelope(AgentModel):
        correlation_id: str
        boss_review_json: str


    class SynthesisRequestEnvelope(AgentModel):
        correlation_id: str
        issue_json: str
        reviews_json: str
        boss_review_json: str


    class SynthesizedRecommendationEnvelope(AgentModel):
        correlation_id: str
        recommendation_json: str


    class RestEvaluateRequestEnvelope(AgentModel):
        api_key: str
        payload_json: str


    class RestEvaluateResponseEnvelope(AgentModel):
        status: str
        response_json: str = ""
        error: str | None = None

else:
    class ReviewRequestEnvelope:
        pass


    class AudienceReviewEnvelope:
        pass


    class BossReviewRequestEnvelope:
        pass


    class BossReviewEnvelope:
        pass


    class SynthesisRequestEnvelope:
        pass


    class SynthesizedRecommendationEnvelope:
        pass


    class RestEvaluateRequestEnvelope:
        pass


    class RestEvaluateResponseEnvelope:
        pass
