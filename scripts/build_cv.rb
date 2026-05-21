#!/usr/bin/env ruby
# frozen_string_literal: true

require 'fileutils'
require 'yaml'

ROOT = File.expand_path('..', __dir__)
DATA_DIR = File.join(ROOT, '_pages')
CV_DIR = File.join(ROOT, 'cv-source')
TEX_PATH = File.join(CV_DIR, 'Curriculum_Vitae.tex')
PDF_PATH = File.join(ROOT, 'files', 'Curriculum_Vitae.pdf')
BUILD_DIR = File.join(ROOT, '.cv-build')
HONORS_PATH = File.join(CV_DIR, 'static', 'honors_awards.tex')

FileUtils.mkdir_p(CV_DIR)
FileUtils.mkdir_p(BUILD_DIR)

def data(name)
  YAML.load_file(File.join(DATA_DIR, "#{name}.yml"))
end

SITE = data('site')
APPOINTMENT = data('appointment')
EDUCATION = data('education')
INTERESTS = data('interests')
PUBLICATIONS = data('publications')
TEACHING = data('teaching')
ACTIVITIES = data('activities')
VISITS = data('visits')
SERVICE = data('service')

CV_ONLY = {
  'professional_designation' => [
    ['Associate of the Society of Actuaries (A.S.A.)', '08/2023']
  ],
  'dissertations' => [
    'Wang, Q. (2023). Characterizing, optimizing and backtesting metrics of risk. \emph{Ph.D. Thesis}. University of Waterloo, Canada.',
    'Wang, Q. (2019). Real option signaling games under asymmetric information and finite option life. \emph{M.Phil. Thesis}. Hong Kong University of Science and Technology, Hong Kong.'
  ]
}.freeze

LATEX_ESCAPE = {
  '\\' => '\\textbackslash{}',
  '&' => '\\&',
  '%' => '\\%',
  '$' => '\\$',
  '#' => '\\#',
  '_' => '\\_',
  '{' => '\\{',
  '}' => '\\}',
  '~' => '\\textasciitilde{}',
  '^' => '\\textasciicircum{}'
}.freeze

def html_to_latex(value)
  text = value.to_s.dup
  text.gsub!(/<strong>(.*?)<\/strong>/m, '\\textbf{\1}')
  text.gsub!(/<em>(.*?)<\/em>/m, '\\emph{\1}')
  text.gsub!(/<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)<\/a>/m, '\2')
  text.gsub!(/<br\s*\/?\s*>/i, '\\\\')
  text.gsub!(/&mdash;/, '--')
  text.gsub!(/&nbsp;/, ' ')
  text.gsub!(/&amp;/, '&')
  text.gsub!(/↗/, '')
  text.gsub!(/—/, '--')
  text.gsub!(/–/, '--')
  text.gsub!(/·/, '\\textperiodcentered{}')
  text.gsub!(/’/, "'")
  text.gsub!(/<[^>]+>/, '')
  text
end

def escape_latex(value)
  html_to_latex(value).gsub(/[\\&%$#_{}~^]/) { |char| LATEX_ESCAPE.fetch(char) }
end

def trusted_latex(value)
  text = html_to_latex(value)
  escaped = text.gsub(/[&%$#_{}~^]/) { |char| LATEX_ESCAPE.fetch(char) }
  escaped.gsub(/\\(textbf|emph)\\\{([^{}]*)\\\}/) { "\\#{Regexp.last_match(1)}{#{Regexp.last_match(2)}}" }
         .gsub(/\\textperiodcentered\\\{\\\}/, '\\textperiodcentered{}')
end

def section(title)
  "\\rule[4pt]{17cm}{0.3pt}\n\\medskip\n{\\large \\bf #{escape_latex(title)}}\n\\medskip\n\n"
end

def two_column_rows(rows)
  body = rows.map do |left, right|
    "#{trusted_latex(left)} & #{trusted_latex(right)}\\\\"
  end.join("\n")

  <<~TEX
    \\begin{center}
    \\renewcommand{\\arraystretch}{1.5}%
    \\begin{tabular}{>{\\raggedright}m{13cm}>{\\raggedleft\\arraybackslash} m{3.5cm}}
    #{body}
    \\end{tabular}
    \\end{center}

  TEX
end

def itemize(items)
  body = items.map { |item| "  \\item #{trusted_latex(item)}" }.join("\n")
  "\\begin{itemize}\n#{body}\n\\end{itemize}\n\n"
end

def enumerate(items)
  body = items.map { |item| "  \\item #{trusted_latex(item)}" }.join("\n")
  "\\begin{enumerate}\n#{body}\n\\end{enumerate}\n\n"
end

def clean_venue(venue)
  trusted_latex(venue)
end

def venue_without_terminal_year(venue)
  venue.to_s.sub(/,\s*20\d{2}\s*\z/, '')
end

def publication_line(pub)
  authors = trusted_latex(pub['authors'])
  title = trusted_latex(pub['title'])
  year = pub['venue'].to_s[/\b(20\d{2})\b/, 1]
  venue = clean_venue(venue_without_terminal_year(pub['venue']))
  prefix = year ? "#{authors} (#{year})." : "#{authors}."
  "#{prefix} #{title}. #{venue}.".gsub(/\s+/, ' ')
end

def activity_items(group_heading)
  ACTIVITIES.flat_map { |column| column['column'] }
            .find { |group| group['heading'] == group_heading }
            .fetch('items')
end

tex = String.new
tex << <<~TEX
  \\documentclass[10pt]{article}
  \\pagestyle{empty}
  \\raggedbottom
  \\raggedright
  \\setlength{\\tabcolsep}{0in}
  \\usepackage{float}
  \\usepackage{array}
  \\usepackage{hyperref}
  \\urlstyle{same}
  \\addtolength{\\topmargin}{-6pc}
  \\addtolength{\\textheight}{10pc}
  \\addtolength{\\oddsidemargin}{-7pc}
  \\addtolength{\\textwidth}{12pc}
  \\setlength{\\evensidemargin}{\\oddsidemargin}
  \\setcounter{page}{1}
  \\renewcommand\\labelenumi{[\\theenumi]}
  \\begin{document}

  {\\Large \\bf Qiuqi Wang, Ph.D., A.S.A.}
  \\medskip

  \\begin{tabular}{l l l}
      Maurice R.~Greenberg School of Risk Science & ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Email: & ~~~~qwang30@gsu.edu\\\\
      Georgia State University & ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Tel: & ~~~~#{escape_latex(SITE['phone'])}\\\\
      35 Broad Street NW & ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Office: & ~~~~Suite 1127\\\\
      Atlanta, GA 30303, USA & ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Website: &~~~ \\url{https://qwangan.github.io/}
  \\end{tabular}
  \\medskip

TEX

tex << section('Academic Appointment')
tex << two_column_rows(APPOINTMENT.map { |item| ["#{item['title']}, #{item['detail']}", item['year']] })

tex << section('Education')
tex << two_column_rows(EDUCATION.map { |item| ["#{item['degree']}, #{item['school']}", item['year']] })

tex << section('Professional Designation')
tex << two_column_rows(CV_ONLY['professional_designation'])

tex << section('Research Interests')
tex << itemize([INTERESTS.join('; ')])

tex << section('Publications and Manuscripts')
PUBLICATIONS.each do |group|
  tex << "{\\bf #{escape_latex(group['heading'])}}\n\n"
  tex << enumerate(group['items'].map { |pub| publication_line(pub) })
end

tex << "{\\bf Dissertations}\n\n"
tex << enumerate(CV_ONLY['dissertations'])

tex << File.read(HONORS_PATH)
tex << "\n"

tex << section('Academic Visits')
tex << two_column_rows(VISITS.map { |visit| ["#{visit['description']} (#{visit['place']})", visit['year']] })

tex << section('Conferences Organized')
organization = activity_items('Conference Organization')
tex << itemize(organization.map { |item| "#{item['description']}, #{item['year']} (#{item['place']})" })

tex << section('Invited Academic Presentations')
invited = activity_items('Invited Presentations')
tex << itemize(invited.map { |item| "#{item['description']}, #{item['year']} (#{item['place']})" })

tex << section('Contributed Academic Presentations')
contributed = activity_items('Conference Presentations')
tex << itemize(contributed.map { |item| "#{item['description']}, #{item['year']} (#{item['place']})" })

tex << section('Teaching Experience')
TEACHING.each do |group|
  tex << "{\\bf #{escape_latex(group['heading'])}}\n\n"
  tex << two_column_rows(group['courses'].map { |course| ["#{course['code']} - #{course['name']}", course['term']] })
end

tex << section('Peer-review Service')
tex << itemize(SERVICE.map { |item| "#{item['label']}: #{item['journals']}" })

tex << <<~TEX
  \\rule[4pt]{17cm}{0.3pt}
  \\begin{center}
      {\\footnotesize Last updated: \\today}
  \\end{center}

  \\end{document}
TEX

File.write(TEX_PATH, tex)
puts "Generated #{TEX_PATH}"

unless ARGV.include?('--tex-only')
  command = ['pdflatex', '-interaction=nonstopmode', '-halt-on-error', '-output-directory', BUILD_DIR, TEX_PATH]
  2.times do
    system(*command) || abort('pdflatex failed')
  end
  built_pdf = File.join(BUILD_DIR, 'Curriculum_Vitae.pdf')
  if ARGV.include?('--draft-output')
    puts "Built draft PDF at #{built_pdf}"
  else
    FileUtils.cp(built_pdf, PDF_PATH)
    puts "Updated #{PDF_PATH}"
  end
end
