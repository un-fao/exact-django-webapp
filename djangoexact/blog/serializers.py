from rest_framework import serializers
import blog.models as models
from api.models import CustomUser
from slugify import slugify


class PostAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "email", "first_name", "last_name"]


class PostSerializer(serializers.ModelSerializer):
    author = PostAuthorSerializer(read_only=True)
    slug = serializers.SlugField(read_only=True)

    class Meta:
        model = models.Post
        fields = "__all__"

    def create(self, validated_data):
        if models.Post.objects.filter(title=validated_data["title"]).exists():
            raise serializers.ValidationError("Post with this title already exists")

        slug = slugify(validated_data["title"])
        user = self.context["request"].user
        post = models.Post.objects.create(author=user, slug=slug, **validated_data)
        return post
