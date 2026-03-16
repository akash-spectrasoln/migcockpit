"""
Project-related API views.
Handles project management.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import psycopg2


class ProjectsListView(APIView):
    """
    API endpoint for listing projects.
    """

    # authentication_classes = [JWTCookieAuthentication]
    # permission_classes = [IsAuthenticated]


    def get(self, request):

        user = request.user
        customer = user.cust_id
        if not customer:
            return Response(
                {"error":"user is not associated with any customer"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        connection = psycopg2.connect(
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            database=customer.cust_db
        )
        cursor = connection.cursor()
        cursor.execute('''SELECT "ID","IDENT","DESCR","IS_ACTIVE","REF_CLIENT" FROM "GENERAL"."PROJECT"''')
        projects_raw = cursor.fetchall()
        cursor.close()
        connection.close()
        
        # Format projects data similar to source data
        projects = []
        for project in projects_raw:
            project_data = {
                'id': project[0],
                'ident': project[1],
                'descr': project[2],
                'is_active': project[3],
                'ref_client': project[4]
            }
            projects.append(project_data)
        
        return Response(projects, status=status.HTTP_200_OK)
