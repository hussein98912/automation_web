from django.urls import path,include
#from .views import signup_api, login_api, logout_api,CategoryListAPIView, ServiceViewSet,ProjectViewSet,chatbot_api,OrderViewSet
#from . import views
#from .views import CurrentUserView,UserListView,OrderStatusUpdateAPIView,UserNotificationListAPIView,ChatHistoryListAPIView,AdminChatHistoryListAPIView
from rest_framework import routers
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from .Views import *



router = routers.DefaultRouter()
router.register(r'services', ServiceViewSet)
router.register(r'projects', ProjectViewSet)
router.register(r"orders", OrderViewSet, basename="order")



urlpatterns = [
    path("api/signup/", signup_api, name="api_signup"),
    path("api/login/", login_api, name="api_login"),
    path("api/logout/", logout_api, name="api_logout"),
    path('api/users/', UserListView.as_view(), name='user-list'),
    path('api/categories/', CategoryListAPIView.as_view(), name='categories-list'),
    path('api/chatbot/', chatbot_api, name='chatbot-api'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/me/', CurrentUserView.as_view(), name='current_user'),
    path('', include(router.urls)),
    path('orders/<int:order_id>/status/', OrderStatusUpdateAPIView.as_view(), name='order-status-update'),
    path('notifications/', UserNotificationListAPIView.as_view(), name='user-notifications'),
    path('chat/history/', ChatHistoryListAPIView.as_view(), name='chat-history'),
    path('api/admin/chat-history/', AdminChatHistoryListAPIView.as_view(), name='admin-chat-history-list'),
    path('payments/create/', create_payment, name='create_payment'),
    path('payments/confirm/', confirm_payment, name='confirm_payment'),
    path("activities/", ActivityListCreateAPIView.as_view(), name="activity-list-create"),
    path('notifications/read/', mark_notifications_read, name='notifications-read'),
    path("dashboard/stats/", dashboard_stats, name="dashboard-stats"),
    path("transactions/", TransactionListView.as_view(), name="transactions"),
    path('video/<int:pk>/', stream_video, name='stream_video'),
    path("project-order/", create_project_order, name="create_project_order"),
    path("orders/<int:order_id>/delete/", delete_order, name="delete_order"),
    path("contact/send/", send_message, name="send_message"),
    path("contact/my-messages/", get_my_messages, name="get_messages"),
    path("contact/my-messages/<int:message_id>/", get_message, name="get_message"),
    path("user/update-profile/", update_profile, name="update_profile"),
    path("user/change-password/", change_password, name="change_password"),
    path('update-instagram/<int:user_id>/', UpdateInstagramIDView.as_view(), name='update-instagram'),
    path('messages/', InstagramMessageView.as_view(), name='messages-post'),
    path('messages/<str:recipient_id>/', InstagramMessageView.as_view(), name='messages-get'),
    path('comments/', InstagramCommentView.as_view(), name='comments-post'),
    path('comments/<str:recipient_id>/', InstagramCommentView.as_view(), name='comments-get'),
    path('instagram/stats/', instagram_stats, name='instagram-stats'),
    path('api/facebook-insights/<str:instagram_account_id>/', FacebookInsightsView.as_view(), name='facebook-insights'),
    path('api/facebook-engagement/<str:instagram_account_id>/', FacebookEngagementInsightsView.as_view(),name='facebook-engagement'),
    path("instagram-profile/<str:instagram_id>/", instagramProfileView.as_view()),
    path("instagram-media-comments/<str:instagram_id>/",InstagramMediaWithCommentsView.as_view()),
    path("facebook/<str:page_id>/profile/", FacebookPageProfileView.as_view(), name="facebook-page-profile"),#yes
    path("facebook/<str:page_id>/posts/", FacebookPostsWithCommentsView.as_view(), name="facebook-posts-comments"),#yes
    path("facebook/stats/", facebook_stats, name="facebook-stats"),
    path('facebook/messages/', FacebookMessageView.as_view(), name='facebook-messages-post'),  # POST
    path('facebook/messages/<str:recipient_page_id>/', FacebookMessageView.as_view(), name='facebook-messages-get'),  # GET
    path('facebook/comments/', FacebookCommentView.as_view(), name='facebook-comments-post'),  # POST
    path('facebook/comments/<str:post_id>/', FacebookCommentView.as_view(), name='facebook-comments-get'),
    path("facebook/insights/<str:page_id>/",FacebookPageInsightsMetricView.as_view(),name="facebook-insights"),  # GET
    path("facebook/insights/multi/<str:page_id>/",FacebookPageInsightsMultiMetricView.as_view(),name="facebook-insights-multi"),
    path("create-session/", CreateBusinessSessionView.as_view(), name="create_session"),
    path("chat/", AIChatView.as_view(), name="ai_chat"),
]
