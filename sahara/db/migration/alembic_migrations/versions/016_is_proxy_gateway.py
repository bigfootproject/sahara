# Copyright 2014 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Add is_proxy_gateway

Revision ID: 016
Revises: 015
Create Date: 2014-11-10 12:47:17.871520

"""

# revision identifiers, used by Alembic.
revision = '016'
down_revision = '015'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('node_group_templates',
                  sa.Column('is_proxy_gateway', sa.Boolean()))
    op.add_column('node_groups',
                  sa.Column('is_proxy_gateway', sa.Boolean()))
    op.add_column('templates_relations',
                  sa.Column('is_proxy_gateway', sa.Boolean()))


def downgrade():
    op.drop_column('templates_relations', 'is_proxy_gateway')
    op.drop_column('node_groups', 'is_proxy_gateway')
    op.drop_column('node_group_templates', 'is_proxy_gateway')
