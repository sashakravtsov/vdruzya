#!/usr/bin/env python
"""Ensure FB 2009–2010 classic modules: likes, places, questions, reviews, polls."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS reactions (
  id bigserial PRIMARY KEY,
  post_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  type varchar(255) NOT NULL DEFAULT 'like',
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS reactions_post_user_type_uniq
  ON reactions (post_id, social_user_id, type);
CREATE INDEX IF NOT EXISTS reactions_post_idx ON reactions (post_id);

CREATE TABLE IF NOT EXISTS places (
  id bigserial PRIMARY KEY,
  name varchar(160) NOT NULL,
  city varchar(120) NOT NULL DEFAULT '',
  address varchar(255) NOT NULL DEFAULT '',
  photo_path varchar(255) NULL,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS places_name_idx ON places (name);

CREATE TABLE IF NOT EXISTS place_checkins (
  id bigserial PRIMARY KEY,
  place_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  message varchar(500) NOT NULL DEFAULT '',
  photo_path varchar(255) NULL,
  created_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS place_checkins_place_idx ON place_checkins (place_id);
CREATE INDEX IF NOT EXISTS place_checkins_user_idx ON place_checkins (social_user_id);
CREATE INDEX IF NOT EXISTS place_checkins_created_idx ON place_checkins (created_at DESC);

CREATE TABLE IF NOT EXISTS place_reviews (
  id bigserial PRIMARY KEY,
  place_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  stars smallint NOT NULL DEFAULT 5,
  body varchar(500) NOT NULL DEFAULT '',
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS place_reviews_uniq
  ON place_reviews (place_id, social_user_id);
CREATE INDEX IF NOT EXISTS place_reviews_place_idx ON place_reviews (place_id);

CREATE TABLE IF NOT EXISTS questions (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  body varchar(500) NOT NULL,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS questions_user_idx ON questions (social_user_id);
CREATE INDEX IF NOT EXISTS questions_created_idx ON questions (created_at DESC);

CREATE TABLE IF NOT EXISTS question_answers (
  id bigserial PRIMARY KEY,
  question_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  body varchar(500) NOT NULL,
  created_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS question_answers_q_idx ON question_answers (question_id);

CREATE TABLE IF NOT EXISTS question_votes (
  id bigserial PRIMARY KEY,
  answer_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS question_votes_uniq
  ON question_votes (answer_id, social_user_id);
CREATE INDEX IF NOT EXISTS question_votes_answer_idx ON question_votes (answer_id);

CREATE TABLE IF NOT EXISTS classic_polls (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  question varchar(500) NOT NULL,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS classic_polls_user_idx ON classic_polls (social_user_id);
CREATE INDEX IF NOT EXISTS classic_polls_created_idx ON classic_polls (created_at DESC);

CREATE TABLE IF NOT EXISTS classic_poll_options (
  id bigserial PRIMARY KEY,
  poll_id bigint NOT NULL,
  body varchar(255) NOT NULL,
  sort_order smallint NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS classic_poll_options_poll_idx ON classic_poll_options (poll_id);

CREATE TABLE IF NOT EXISTS classic_poll_votes (
  id bigserial PRIMARY KEY,
  poll_id bigint NOT NULL,
  option_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS classic_poll_votes_uniq
  ON classic_poll_votes (poll_id, social_user_id);
CREATE INDEX IF NOT EXISTS classic_poll_votes_option_idx ON classic_poll_votes (option_id);

CREATE TABLE IF NOT EXISTS photo_reactions (
  id bigserial PRIMARY KEY,
  photo_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  type varchar(255) NOT NULL DEFAULT 'like',
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS photo_reactions_uniq
  ON photo_reactions (photo_id, social_user_id, type);
CREATE INDEX IF NOT EXISTS photo_reactions_photo_idx ON photo_reactions (photo_id);

CREATE TABLE IF NOT EXISTS comment_reactions (
  id bigserial PRIMARY KEY,
  comment_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  type varchar(255) NOT NULL DEFAULT 'like',
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS comment_reactions_uniq
  ON comment_reactions (comment_id, social_user_id, type);
CREATE INDEX IF NOT EXISTS comment_reactions_comment_idx ON comment_reactions (comment_id);

CREATE TABLE IF NOT EXISTS post_tags (
  id bigserial PRIMARY KEY,
  post_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  tagged_by_id bigint NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS post_tags_uniq ON post_tags (post_id, social_user_id);
CREATE INDEX IF NOT EXISTS post_tags_user_idx ON post_tags (social_user_id);

CREATE TABLE IF NOT EXISTS classic_group_docs (
  id bigserial PRIMARY KEY,
  community_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  title varchar(200) NOT NULL,
  body text NOT NULL DEFAULT '',
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS classic_group_docs_community_idx ON classic_group_docs (community_id);
CREATE INDEX IF NOT EXISTS classic_group_docs_created_idx ON classic_group_docs (created_at DESC);

CREATE TABLE IF NOT EXISTS photo_comment_reactions (
  id bigserial PRIMARY KEY,
  comment_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  type varchar(255) NOT NULL DEFAULT 'like',
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS photo_comment_reactions_uniq
  ON photo_comment_reactions (comment_id, social_user_id, type);

CREATE TABLE IF NOT EXISTS group_comment_reactions (
  id bigserial PRIMARY KEY,
  comment_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  type varchar(255) NOT NULL DEFAULT 'like',
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS group_comment_reactions_uniq
  ON group_comment_reactions (comment_id, social_user_id, type);

CREATE TABLE IF NOT EXISTS group_post_reactions (
  id bigserial PRIMARY KEY,
  post_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  type varchar(255) NOT NULL DEFAULT 'like',
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS group_post_reactions_uniq
  ON group_post_reactions (post_id, social_user_id, type);

CREATE TABLE IF NOT EXISTS relationship_requests (
  id bigserial PRIMARY KEY,
  requester_id bigint NOT NULL,
  partner_id bigint NOT NULL,
  status varchar(20) NOT NULL DEFAULT 'pending',
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS relationship_requests_uniq
  ON relationship_requests (requester_id, partner_id);
CREATE INDEX IF NOT EXISTS relationship_requests_partner_idx
  ON relationship_requests (partner_id, status);

CREATE TABLE IF NOT EXISTS feed_hides (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  actor_id bigint NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS feed_hides_uniq
  ON feed_hides (social_user_id, actor_id);
CREATE INDEX IF NOT EXISTS feed_hides_user_idx ON feed_hides (social_user_id);

CREATE TABLE IF NOT EXISTS feed_story_hides (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  story_key varchar(80) NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS feed_story_hides_uniq
  ON feed_story_hides (social_user_id, story_key);

CREATE TABLE IF NOT EXISTS family_links (
  id bigserial PRIMARY KEY,
  from_user_id bigint NOT NULL,
  to_user_id bigint NOT NULL,
  kind varchar(20) NOT NULL DEFAULT 'sibling',
  status varchar(20) NOT NULL DEFAULT 'pending',
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS family_links_uniq
  ON family_links (from_user_id, to_user_id);
CREATE INDEX IF NOT EXISTS family_links_to_idx
  ON family_links (to_user_id, status);
"""

ALTER = """
ALTER TABLE places ADD COLUMN IF NOT EXISTS photo_path varchar(255) NULL;
ALTER TABLE place_checkins ADD COLUMN IF NOT EXISTS photo_path varchar(255) NULL;
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
        cur.execute(ALTER)
        for t in (
            "reactions", "places", "place_checkins", "place_reviews",
            "questions", "question_answers", "question_votes",
            "classic_polls", "classic_poll_options", "classic_poll_votes",
            "photo_reactions", "comment_reactions", "post_tags", "classic_group_docs",
            "photo_comment_reactions", "group_comment_reactions", "group_post_reactions",
            "relationship_requests", "feed_hides", "feed_story_hides", "family_links",
        ):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), t
        for col in ("places.photo_path", "place_checkins.photo_path"):
            table, name = col.split(".")
            cur.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name=%s AND column_name=%s",
                [table, name],
            )
            assert cur.fetchone(), col
    print("OK   2010 classic schema (likes/places/polls/tags/docs/rel)")


if __name__ == "__main__":
    main()
