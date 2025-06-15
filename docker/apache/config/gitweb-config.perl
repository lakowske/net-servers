#!/usr/bin/perl
# Gitweb configuration file for net-servers project

# Repository directory where Git repos are stored
our $projectroot = "/var/git/repositories";

# Site configuration
our $site_name = "Net Servers - Git Repositories";
our $site_header = "/var/www/gitweb-header.html";
our $site_footer = "/var/www/gitweb-footer.html";

# Navigation
our $home_link = "/git";
our $home_link_str = "projects";

# Contact info
our $site_contact = "admin@local.dev";

# Show repository owner
our $omit_owner = 0;

# Show age column
our $omit_age_column = 0;

# Projects list settings
our $projects_list_description_width = 50;

# Return true (required for Perl modules)
1;
