#!/usr/bin/env perl
# Native POSIX base installation metadata. Only core Perl modules are used.
use strict;
use warnings;
use Encode qw(decode encode FB_CROAK);
use Fcntl qw(:flock);
use JSON::PP ();

my $package = 'codex-cross-project-engineering-assistant';
my $market = 'cp-assistant-base';
my $json = JSON::PP->new->utf8->canonical;
my $mode = shift @ARGV // '';

sub read_json {
    my ($stream) = @_;
    my $text = '';
    while (1) {
        my $count = read($stream, my $part, 65536);
        die "JSON input unreadable\n" unless defined $count;
        last if $count == 0;
        $text .= $part;
        die "JSON input too large\n" if length($text) > 4194304;
    }
    return $json->decode($text);
}

sub json_file {
    my ($path) = @_;
    open my $stream, '<:raw', $path or die "Cannot read managed metadata\n";
    return read_json($stream);
}

sub registration {
    my ($root) = @_;
    my $profile = json_file("$root/config/desktop-host-contract-v1.json")->{wire_profiles}->{plugin_json}->{'plugin-list-v1'};
    my $version = json_file("$root/.codex-plugin/plugin.json")->{version};
    my $doc = read_json(\*STDIN);
    return 'UNVERIFIED' unless ref($doc) eq 'HASH' && keys(%$doc)==2 &&
        ref($doc->{installed}) eq 'ARRAY' && ref($doc->{available}) eq 'ARRAY';
    my $id = "$package\@$market";
    my $target;
    for my $row (@{$doc->{installed}}, @{$doc->{available}}) {
        return 'UNVERIFIED' unless ref($row) eq 'HASH';
        my ($rid,$name,$place) = map { $row->{$_} // '' } qw(pluginId name marketplaceName);
        next unless $rid eq $id || $name eq $package || $place eq $market;
        return 'IDENTITY_CONFLICT' if $target || $rid ne $id || $name ne $package || $place ne $market;
        $target = $row;
    }
    return 'MISSING' unless $target;
    my %required = map { $_ => 1 } @{$profile->{required_target_fields}};
    my %optional = map { $_ => 1 } @{$profile->{optional_target_fields}};
    return 'UNVERIFIED' if grep { !exists $target->{$_} } keys %required;
    for my $key (keys %$target) {
        next if $required{$key};
        return 'UNVERIFIED' unless $optional{$key} && (ref($target->{$key}) eq 'HASH' ||
            JSON::PP->new->allow_nonref->encode($target->{$key}) =~ /^"/);
    }
    return 'UNVERIFIED' unless JSON::PP::is_bool($target->{installed}) && JSON::PP::is_bool($target->{enabled});
    return 'UNVERIFIED' unless ($target->{version} // '') =~ /^\d+\.\d+\.\d+$/ &&
        (grep { $_ eq ($target->{installPolicy}//'') } @{$profile->{install_policies}}) &&
        (grep { $_ eq ($target->{authPolicy}//'') } @{$profile->{auth_policies}});
    return 'VERSION_MISMATCH' unless $target->{version} eq $version;
    return 'NOT_INSTALLED' unless $target->{installed};
    return $target->{enabled} ? 'ACTIVE' : 'DISABLED';
}

if ($mode eq 'registration') {
    my $status = eval { registration($ARGV[0]) };
    print(($@ ? 'UNVERIFIED' : $status), "\n");
} elsif ($mode eq 'state-read') {
    my ($path,$root) = @ARGV;
    my $state = eval { json_file($path) };
    my $expected = decode('UTF-8',$root,FB_CROAK);
    die "Base state is not a JSON object\n" unless ref($state) eq 'HASH';
    my $phase = exists($state->{status}) ? ($state->{status} // '') : 'INSTALLED';
    die "Base state identity or format is invalid. Inspect the existing state.\n" unless
        ref($state) eq 'HASH' && JSON::PP->new->allow_nonref->encode($state->{schema_version}) eq '1' && ($state->{package}//'') eq $package &&
        ($state->{marketplace}//'') eq $market && ($state->{market_root}//'') eq $expected &&
        $phase =~ /\A(?:INSTALLING|INSTALLED|RECOVERY_REQUIRED)\z/;
    print "$phase\n";
} elsif ($mode eq 'state-write') {
    my ($root,$status) = @ARGV;
    my $expected = decode('UTF-8',$root,FB_CROAK);
    print $json->encode({schema_version=>1,package=>$package,marketplace=>$market,
        market_root=>$expected,status=>$status}), "\n";
} elsif ($mode eq 'lock') {
    open my $lock, '>&=9' or die "Base installation lock unavailable\n";
    flock($lock,LOCK_EX|LOCK_NB) or die "Another base installation is active. Retry when it finishes.\n";
} else {
    die "Unknown base metadata operation\n";
}
