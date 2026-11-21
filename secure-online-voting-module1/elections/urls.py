from django.urls import path
from . import views

app_name = 'elections'
urlpatterns = [
    path('', views.election_list, name='list'),
    path('create/', views.election_create, name='create'),
    path('<int:pk>/', views.election_detail, name='detail'),
    path('<int:pk>/candidates/add/', views.candidate_add, name='candidate_add'),
    path('candidates/<int:pk>/edit/', views.candidate_edit, name='candidate_edit'),
    path('candidates/<int:pk>/delete/', views.candidate_remove, name='candidate_remove'),
    path('<int:pk>/schedule/', views.schedule_election, name='schedule'),
    path('<int:pk>/eligibility/', views.approve_voter, name='eligibility'),
    path('<int:pk>/vote/', views.vote, name='vote'),
    path('<int:pk>/edit/', views.election_edit, name='edit'),
path('<int:pk>/delete/', views.election_delete, name='delete'),
]
