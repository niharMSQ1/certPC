from django.urls import path
from . import views

urlpatterns = [
    path('api/frameworks/', views.get_frameworks),
    path('api/create_framework/', views.create_framework),
    path('api/upload_policy_pdf/', views.upload_policy_pdf),
    path('api/policy_diffs/<int:version_id>/', views.policy_diffs),
    path('editor/<int:version_id>/', views.edit_policy),
    path('editor/', views.edit_policy),
    path('api/generate_pdf/', views.generate_pdf),
    path('api/change_history/<int:policy_id>/', views.policy_change_history),
]