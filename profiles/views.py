from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Profile
from .serializers import ProfileSerializer, PublicProfileSerializer


class CreateProfileView(APIView):
    """'শুরু করুন' বাটন"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        if Profile.objects.filter(user=request.user).exists():
            return Response({"error": "প্রোফাইল আগেই তৈরি করা আছে।"}, status=400)
        s = ProfileSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        s.save(user=request.user)
        return Response(s.data, status=status.HTTP_201_CREATED)


class MyProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_profile(self, request):
        return get_object_or_404(Profile, user=request.user)

    def get(self, request):
        profile = self.get_profile(request)
        return Response(ProfileSerializer(profile, context={"request": request}).data)

    def patch(self, request):
        profile = self.get_profile(request)
        s = ProfileSerializer(profile, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)

    def delete(self, request):
        """শুধু ছবি মুছে ফেলার জন্য নয়, পুরো প্রোফাইল মুছে ফেলে"""
        self.get_profile(request).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfilePhotoView(APIView):
    """ছবি আলাদাভাবে আপলোড/মুছা"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        profile = get_object_or_404(Profile, user=request.user)
        photo = request.FILES.get("photo")
        if not photo:
            return Response({"error": "ছবি পাঠান (field: photo)।"}, status=400)
        s = ProfileSerializer(profile, data={"photo": photo}, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        if profile.photo:
            profile.photo.delete(save=False)
        s.save()
        return Response(s.data)

    def delete(self, request):
        profile = get_object_or_404(Profile, user=request.user)
        if profile.photo:
            profile.photo.delete(save=False)
            profile.photo = None
            profile.save()
        return Response(ProfileSerializer(profile, context={"request": request}).data)


class PublicProfileView(APIView):
    """বিক্রেতার প্রোফাইল দেখা"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        profile = get_object_or_404(Profile, user_id=user_id)
        return Response(PublicProfileSerializer(profile, context={"request": request}).data)