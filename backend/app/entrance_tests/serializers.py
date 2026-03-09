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
