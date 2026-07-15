"""Service layer: business logic that API routes delegate to.

Introduced for the Attendance Verification Engine — routes in
`app/api/v1/endpoints/` should stay thin (parse the request, call a
service, translate the result/exception into an HTTP response), with the
actual domain logic living here instead. Existing endpoints
(auth/students/teachers/registration/diagnostics) predate this convention
and are not being retrofitted to it in this milestone — only new
attendance-verification logic is required to follow it.
"""
