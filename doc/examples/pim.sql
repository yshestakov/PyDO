CREATE TABLE contact (
  id integer not null primary key,
  first_name text,
  last_name text not null,
  address_id1 integer references address,
  address_id2 integer references address,
  email1 text,
  email2 text,
  work_phone text,
  home_phone text,
  mobile_phone text
);

CREATE TABLE address (
  id integer not null primary key,
  line1 text,
  line2 text,
  town text,
  state text,
  country text,
  postal_code text
);

CREATE TABLE note (
  id integer not null primary key,
  title text,
  body text not null,
  created timestamp
);

CREATE TABLE contact_note (
  contact_id integer references contact,
  note_id integer references note,
  primary key (contact_id, note_id)
);
  

