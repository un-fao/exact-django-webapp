from django.urls import path

from . import views

app_name = "admin_scripts"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("jobs/", views.jobs_list, name="jobs-list"),
    path("jobs/partial/", views.jobs_list_partial, name="jobs-list-partial"),
    path("example-script/", views.example_script, name="example-script"),
    path("compile-scenarios/", views.compile_scenarios, name="compile-scenarios"),
    path("compile-scenarios/export/", views.compile_scenarios_export, name="compile-scenarios-export"),
    path("compile-scenarios/htmx/module-types/", views.htmx_module_types, name="htmx-module-types"),
    path("compile-scenarios/htmx/fields/", views.htmx_fields, name="htmx-fields"),
    path("compile-scenarios/htmx/values/", views.htmx_values, name="htmx-values"),
    path("compile-scenarios/htmx/filters/", views.htmx_filters, name="htmx-filters"),
    path("compile-scenarios/htmx/add-change/", views.htmx_add_change, name="htmx-add-change"),
    path("compile-scenarios/htmx/run-scenario/", views.htmx_run_scenario, name="htmx-run-scenario"),
    path("compile-scenarios/htmx/enqueue-job/", views.htmx_enqueue_job, name="htmx-enqueue-job"),
    path("compile-scenarios/htmx/add-scenario/", views.htmx_add_scenario, name="htmx-add-scenario"),
    path("compile-scenarios/htmx/job-status/", views.htmx_job_status, name="htmx-job-status"),
    path("compile-scenarios/htmx/cancel-job/", views.htmx_cancel_job, name="htmx-cancel-job"),
    path("test-modules/", views.test_modules, name="test-modules"),
    path("test-modules/<int:run_id>/", views.test_modules_detail, name="test-modules-detail"),
    path("test-modules/<int:run_id>/status/", views.test_modules_status, name="test-modules-status"),
]
