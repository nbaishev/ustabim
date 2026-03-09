from rest_framework import serializers


class EntranceQuizAnswerItemSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(min_value=1)
    option_id = serializers.IntegerField(min_value=1)


class EntranceQuizSubmitSerializer(serializers.Serializer):
    answers = EntranceQuizAnswerItemSerializer(many=True)

    def validate_answers(self, value):
        question_ids = [item["question_id"] for item in value]
        if len(question_ids) != len(set(question_ids)):
            raise serializers.ValidationError("Duplicate answers for the same question are not allowed")
        return value


class FreeCourseBenefitClaimSerializer(serializers.Serializer):
    target_course_id = serializers.CharField()


class EntranceQuizActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("start", "submit", "claim"))
    attempt_id = serializers.UUIDField(required=False)
    answers = EntranceQuizAnswerItemSerializer(many=True, required=False)
    target_course_id = serializers.CharField(required=False)

    def validate(self, attrs):
        action = attrs["action"]
        if action == "submit":
            if "attempt_id" not in attrs:
                raise serializers.ValidationError({"attempt_id": "This field is required for submit action"})
            answers = attrs.get("answers", [])
            question_ids = [item["question_id"] for item in answers]
            if len(question_ids) != len(set(question_ids)):
                raise serializers.ValidationError({"answers": "Duplicate answers for the same question are not allowed"})
        elif action == "claim":
            if not attrs.get("target_course_id"):
                raise serializers.ValidationError({"target_course_id": "This field is required for claim action"})
        return attrs
