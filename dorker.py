import github3
import github3.exceptions
import os
import re
import time


def two_factor():
    code = None
    while not code:
        input("Two-factor authentication code: ")
    return code


class Dorker:
    def __init__(self, args):
        self.user = args["user"]
        self.users_filename = args["users_filename"]
        self.org = args["org"]
        self.orgs_filename = args["orgs_filename"]
        self.repo = args["repo"]
        self.dorks_filename = args["dorks_filename"]
        self.output_dir = args["output_dir"]
        self.valid_items_filename = args["valid_items_filename"]

        self.gh = None

    def authenticate(self):
        gh_user = os.getenv("GH_USER", None)
        gh_pass = os.getenv("GH_PASS", None)
        gh_token = os.getenv("GH_TOKEN", None)
        gh_url = os.getenv("GH_URL", None)

        if gh_url:
            client = github3.GitHubEnterprise(url=gh_url)
        else:
            client = github3.GitHub()

        client.login(
            username=gh_user,
            password=gh_pass,
            token=gh_token,
            two_factor_callback=two_factor,
        )

        # Check if login worked
        try:
            client.me()
            print("Successfully authenticated.")
        except github3.exceptions.AuthenticationFailed:
            print(
                "Login failed. Proceeding as unauthenticated user, with low rate limit."
            )

        self.gh = {
            "client": client,
            "reset": {
                "search": None,
                "core": None,
            },
        }

    def get_filename(self, dork):
        """Get a filename to store results for this query. In most cases this will just be the dork string sans any
        non-alphanumeric characters, but if there are collisions it will add a numeric increment to the end of the
        filename to avoid overwriting."""
        filename_base = re.sub("[^a-zA-Z0-9 _]+", "", dork)
        filename_base = re.sub(" ", "_", filename_base)
        increment = 0
        uniq = ""
        while True:
            if os.path.exists(
                os.path.join(self.output_dir, filename_base + uniq + ".txt")
            ):
                increment += 1
                uniq = "_" + str(increment)
            else:
                return filename_base + uniq + ".txt"

    def handle_rate_limit(self, resource="core"):
        """Sleep until the relevant rate limit resets."""
        rate_limit_resp = self.gh["client"].rate_limit()
        rate_limit_reset = rate_limit_resp["resources"][resource]["reset"]
        self.gh["reset"][resource] = rate_limit_reset
        now = int(time.time())
        if self.gh["reset"][resource] and self.gh["reset"][resource] > now:
            sleep_duration = self.gh["reset"][resource] - now + 1
            print(
                "Github {} rate limit hit. Sleeping {} seconds.".format(
                    resource,
                    sleep_duration,
                )
            )
            time.sleep(sleep_duration)

    def check_user_exists(self, user):
        """Check if the user exists before doing the query. This helps reduce the number of calls to the search API,
        which has a much lower rate limit."""
        user = user.strip()
        try:
            self.gh["client"].user(user)
            return True
        except github3.exceptions.ForbiddenError:
            self.handle_rate_limit("core")
            return self.check_user_exists(user)
        except github3.exceptions.NotFoundError:
            print("User {} doesn't exist".format(user))
            return False

    def check_org_exists(self, org):
        """Check if the org exists before doing the query. This helps reduce the number of calls to the search API,
        which has a much lower rate limit."""
        org = org.strip()
        try:
            self.gh["client"].organization(org)
            return True
        except github3.exceptions.ForbiddenError:
            self.handle_rate_limit("core")
            return self.check_org_exists(org)
        except github3.exceptions.NotFoundError:
            print("Org {} doesn't exist".format(org))
            return False

    def search(self, query, output_filename):
        """Search Github and print/log results."""
        print("Searching: " + query)
        try:
            found = False
            search_results = self.gh["client"].search_code(query)
            for result in search_results:
                found = True
                formatted_result = "\n".join(
                    [
                        "Found result for {dork}",
                        "Text matches: {text_matches}",
                        "File path: {path}",
                        "Score: {score}",
                        "File URL: {url}",
                    ]
                ).format(
                    dork=query,
                    text_matches=result.text_matches,
                    path=result.path,
                    score=result.score,
                    url=result.url,
                )
                if output_filename:
                    with open(
                        os.path.join(self.output_dir, output_filename), "a+"
                    ) as output_file:
                        output_file.write(formatted_result + "\n\n")
                print(formatted_result)
            if not found:
                with open(
                    os.path.join(self.output_dir, output_filename), "a+"
                ) as output_file:
                    output_file.write("No results for {}\n\n".format(query))
                print("No results for " + query)
            return True  # Valid user with code results
        except github3.exceptions.ForbiddenError as e:
            self.handle_rate_limit("search")
            return self.search(query, output_filename)
        except github3.exceptions.GitHubError as e:
            if e.code == 422:
                return False
            raise e
        except Exception as e:
            raise e

    def search_with_filter(self, dork, filter_name, filter_value, output_filename):
        """Strip search values of whitespace, form the query, and call the search function."""
        stripped_value = filter_value.strip()
        if not stripped_value:
            return False
        query = "{dork} {filter}:{value}".format(
            dork=dork, filter=filter_name, value=stripped_value
        )
        return self.search(query, output_filename)

    def search_with_users_file(self, dork, output_filename):
        if not self.valid_items_filename:
            # Search without saving whether the user exists/has public code
            with open(self.users_filename, "r") as users_file:
                for user in users_file:
                    if not self.check_user_exists(user):
                        continue
                    self.search_with_filter(dork, "user", user, output_filename)
        elif self.valid_items_filename and os.path.exists(self.valid_items_filename):
            # We already have a list of valid users, so don't need to check
            with open(self.valid_items_filename, "r") as users_file:
                for user in users_file:
                    self.search_with_filter(dork, "user", user, output_filename)
        else:
            # We haven't yet filtered the users, but we want to save the valid ones
            with open(self.users_filename, "r") as users_file:
                for user in users_file:
                    if not self.check_user_exists(user):
                        continue
                    user_has_code = self.search_with_filter(
                        dork, "user", user, output_filename
                    )
                    if user_has_code:
                        with open(self.valid_items_filename, "a+") as valid_users_file:
                            valid_users_file.write(user)

    def search_with_orgs_file(self, dork, output_filename):
        if not self.valid_items_filename:
            # Search without saving whether the org exists/has public code
            with open(self.orgs_filename, "r") as orgs_file:
                for org in orgs_file:
                    if not self.check_org_exists(org):
                        continue
                    self.search_with_filter(dork, "org", org, output_filename)
        elif self.valid_items_filename and os.path.exists(self.valid_items_filename):
            # We already have a list of valid orgs, so don't need to check
            with open(self.valid_items_filename, "r") as orgs_file:
                for org in orgs_file:
                    self.search_with_filter(dork, "org", org, output_filename)
        else:
            # We haven't yet filtered the orgs, but we want to save the valid ones
            with open(self.orgs_filename, "r") as orgs_file:
                for org in orgs_file:
                    if not self.check_org_exists(org):
                        continue
                    org_has_code = self.search_with_filter(
                        dork, "org", org, output_filename
                    )
                    if org_has_code:
                        with open(self.valid_items_filename, "a+") as valid_orgs_file:
                            valid_orgs_file.write(org)

    def dork(self):
        with open(self.dorks_filename, "r") as dorks_file:
            for dork in dorks_file:
                dork = dork.strip()
                if not dork or dork[0] in "#;":
                    continue

                print(dork)

                output_filename = None
                if self.output_dir:
                    output_filename = self.get_filename(dork)

                if self.user:
                    # Single user
                    self.search_with_filter(dork, "user", self.user, output_filename)
                elif self.users_filename:
                    # Users file
                    self.search_with_users_file(dork, output_filename)
                elif self.org:
                    # Single org
                    self.search_with_filter(dork, "org", self.org, output_filename)
                elif self.orgs_filename:
                    # Orgs file
                    self.search_with_orgs_file(dork, output_filename)
                elif self.repo:
                    self.search_with_filter(dork, "repo", self.repo, output_filename)

    def run(self):
        self.authenticate()
        self.dork()
