from django.urls import path
from . import views as v

urlpatterns = [
    path("", v.ProductListCreateView.as_view()),
    path("mine/", v.MyProductsView.as_view()),
    path("saved/", v.SavedListView.as_view()),
    path("categories/", v.CategoryListView.as_view()),
    path("areas/", v.AreaListView.as_view()),
    path("safety-tips/", v.SafetyTipsView.as_view()),
    path("report-reasons/", v.ReportReasonsView.as_view()),
    path("sellers/<int:user_id>/", v.SellerProfileView.as_view()),
    path("block/<int:user_id>/", v.BlockUserView.as_view()),
    path("<int:pk>/", v.ProductDetailView.as_view()),
    path("<int:pk>/mark-sold/", v.ProductStatusView.as_view(new_status="sold")),
    path("<int:pk>/relist/", v.ProductStatusView.as_view(new_status="active")),
    path("<int:pk>/save/", v.SaveProductView.as_view()),
    path("<int:pk>/report/", v.ProductReportView.as_view()),
    path("<int:pk>/contact/", v.ProductContactView.as_view()),
]