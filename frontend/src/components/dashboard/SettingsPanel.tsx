'use client';

import { useState } from 'react';
import { User, Mail, Lock, Bell, Trash2, LogOut } from 'lucide-react';

type SettingsTab = 'account' | 'notifications' | 'security' | 'danger';

export function SettingsPanel() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('account');

  const tabs = [
    { id: 'account' as SettingsTab, label: 'Account', icon: User },
    { id: 'notifications' as SettingsTab, label: 'Notifications', icon: Bell },
    { id: 'security' as SettingsTab, label: 'Security', icon: Lock },
    { id: 'danger' as SettingsTab, label: 'Danger Zone', icon: Trash2 },
  ];

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-5xl mx-auto p-6 lg:p-8 space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold text-text-primary mb-2">
            Settings
          </h1>
          <p className="text-text-secondary">
            Manage your account settings and preferences
          </p>
        </div>

        <div className="grid lg:grid-cols-4 gap-8">
          {/* Tabs sidebar */}
          <div className="lg:col-span-1">
            <nav className="space-y-1">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors ${
                      activeTab === tab.id
                        ? 'bg-surface-overlay text-text-primary'
                        : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
                    }`}
                  >
                    <Icon className={`h-5 w-5 ${
                      activeTab === tab.id ? 'text-brand-primary' : 'text-text-tertiary'
                    }`} />
                    <span className="text-sm font-medium">{tab.label}</span>
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Content */}
          <div className="lg:col-span-3 space-y-6">
            {activeTab === 'account' && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-text-primary mb-4">
                    Account Information
                  </h2>
                  
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-text-primary mb-2">
                        Full Name
                      </label>
                      <input
                        type="text"
                        defaultValue="John Doe"
                        className="w-full px-4 py-2.5 rounded-lg border border-border-default bg-surface-elevated text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-text-primary mb-2">
                        Email Address
                      </label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-text-tertiary" />
                        <input
                          type="email"
                          defaultValue="john@example.com"
                          className="w-full pl-11 pr-4 py-2.5 rounded-lg border border-border-default bg-surface-elevated text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-text-primary mb-2">
                        Bio
                      </label>
                      <textarea
                        rows={4}
                        defaultValue="Experienced frontend engineer passionate about building great user experiences."
                        className="w-full px-4 py-2.5 rounded-lg border border-border-default bg-surface-elevated text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent resize-none"
                      />
                    </div>

                    <button className="px-6 py-2.5 rounded-lg bg-brand-primary text-text-inverse font-medium hover:bg-brand-primary-hover transition-colors">
                      Save Changes
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'notifications' && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-text-primary mb-4">
                    Notification Preferences
                  </h2>
                  
                  <div className="space-y-4">
                    {[
                      { id: 'tailoring-complete', label: 'Tailoring Complete', description: 'Get notified when a new tailoring is ready' },
                      { id: 'experience-processed', label: 'Experience Processed', description: 'When your resume or GitHub data is processed' },
                      { id: 'weekly-summary', label: 'Weekly Summary', description: 'Receive a weekly summary of your activity' },
                      { id: 'tips', label: 'Tips & Recommendations', description: 'Get tips to improve your applications' },
                    ].map((notification) => (
                      <label
                        key={notification.id}
                        className="flex items-start gap-4 p-4 rounded-lg border border-border-subtle hover:border-border-default transition-colors cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          defaultChecked={notification.id !== 'tips'}
                          className="mt-1 h-4 w-4 rounded border-border-default text-brand-primary focus:ring-brand-primary"
                        />
                        <div className="flex-1">
                          <p className="font-medium text-text-primary">
                            {notification.label}
                          </p>
                          <p className="text-sm text-text-secondary mt-0.5">
                            {notification.description}
                          </p>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'security' && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-text-primary mb-4">
                    Security Settings
                  </h2>
                  
                  <div className="space-y-4">
                    <div className="p-4 rounded-lg border border-border-subtle">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-medium text-text-primary">
                            Change Password
                          </p>
                          <p className="text-sm text-text-secondary mt-1">
                            Last changed 3 months ago
                          </p>
                        </div>
                        <button className="px-4 py-2 rounded-lg border border-border-default text-text-primary text-sm font-medium hover:bg-surface-overlay transition-colors">
                          Update
                        </button>
                      </div>
                    </div>

                    <div className="p-4 rounded-lg border border-border-subtle">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-medium text-text-primary">
                            Two-Factor Authentication
                          </p>
                          <p className="text-sm text-text-secondary mt-1">
                            Add an extra layer of security
                          </p>
                        </div>
                        <button className="px-4 py-2 rounded-lg bg-brand-primary text-text-inverse text-sm font-medium hover:bg-brand-primary-hover transition-colors">
                          Enable
                        </button>
                      </div>
                    </div>

                    <div className="p-4 rounded-lg border border-border-subtle">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-medium text-text-primary">
                            Active Sessions
                          </p>
                          <p className="text-sm text-text-secondary mt-1">
                            2 active sessions
                          </p>
                        </div>
                        <button className="px-4 py-2 rounded-lg border border-border-default text-text-primary text-sm font-medium hover:bg-surface-overlay transition-colors">
                          Manage
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'danger' && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-text-primary mb-4">
                    Danger Zone
                  </h2>
                  
                  <div className="space-y-4">
                    <div className="p-4 rounded-lg border border-error-border bg-error-bg">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-medium text-text-primary">
                            Log Out All Sessions
                          </p>
                          <p className="text-sm text-text-secondary mt-1">
                            You will be logged out from all devices
                          </p>
                        </div>
                        <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-error text-error text-sm font-medium hover:bg-error hover:text-text-inverse transition-colors flex-shrink-0">
                          <LogOut className="h-4 w-4" />
                          Log Out
                        </button>
                      </div>
                    </div>

                    <div className="p-4 rounded-lg border border-error-border bg-error-bg">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-medium text-text-primary">
                            Delete Account
                          </p>
                          <p className="text-sm text-text-secondary mt-1">
                            Permanently delete your account and all data
                          </p>
                        </div>
                        <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-error text-text-inverse text-sm font-medium hover:bg-error/90 transition-colors flex-shrink-0">
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
