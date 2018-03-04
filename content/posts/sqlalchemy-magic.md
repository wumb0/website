Title: sqlalchemy Magic
Date: 2018-03-04 00:06
Category: Programming
Tags: python sqlalchemy
Slug: sqlalchemy-magic
Authors: wumb0

I was writing a plugin for [CTFd](https://github.com/CTFd/CTFd) and I was faced with an interesting problem: how the hell do I add a column (attribue) to a parent table without modifying that table (or model object)???  
I was trying to assign an extra attribute to the `Teams` model; a one-to-many relationship between bracket and team so I could have `Teams.chal_bracket` and `Bracket.teams`, but again without modifying the `Teams` model.  
I had actually tried overriding the `Teams` model and also adding a row on the fly, but neither of those worked. I ended up with the solution below:
[[more]]
```python
# secondary table for team<->bracket associations
tb = db.Table("team_bracket",
              db.Column("bracket_id", db.Integer, db.ForeignKey("bracket.id")),
              db.Column("team_id", db.Integer, db.ForeignKey("teams.id"))
              )


class Bracket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, index=True, unique=True)
    hidden = db.Column(db.Boolean)
    # super hacked up way to get the chal_bracket attribute on the parent
    # model class (Teams) without actually modifying it
    teams = db.relationship("Teams", backref=db.backref("chal_bracket", uselist=False),
                            secondary=tb, primaryjoin=id == tb.c.bracket_id,
                            secondaryjoin=Teams.id == tb.c.team_id)
```
Breaking this down:  
<ul>
<li>The table `tb` defines the table `team_bracket`, which associates a team and a bracket by id</li>
<li>The `Bracket` class, which represents a database table and has an attribute teams</li>
<li>The `teams` attribute has a `backref` that allows access to the bracket of a team using the `Teams.chal_bracket` attribue. The attribute is back-populated by sqlalchemy internally; this means the table isn't changed, but sqlalchemy does the work for you! The `uselist=False` argument is used so that `team.chal_bracket` returns just the bracket object and not a list of length 1 with the bracket object in it.</li>
<li>The `teams` attribute also defines two joins: a `primaryjoin` that links the `id` of the object to the bracket id and a `secondaryjoin` that links the team id to the `team_id` of the object. This makes it so that you can get all of the teams associated with a bracket by just doing `Bracket.teams` and also get the bracket associated with a team by doing `Teams.chal_bracket`.</li>
</ul>

Normally you would have to define a relationship in the parent as follows:
```python
class Teams(db.Model):
...
    chal_bracket_id = db.Column(db.Integer, db.ForeignKey("bracket.id"))
    chal_bracket = db.Relationship("Bracket")
```
But because of this hack you don't need to modify the parent model to accomplish the exact same thing.  
Pretty cool.  
