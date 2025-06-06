import React, { useEffect } from 'react'
import { useContext } from 'use-context-selector'
import { login } from '@/service/common'
import { useRouter, useSearchParams } from 'next/navigation'
import Toast from '@/app/components/base/toast'
import I18NContext from '@/context/i18n'
function getQueryParam(param: string) {
  const search = window.location.search.substring(1) // 去掉开头的问号
  const params = search.split('&')
  for (let i = 0; i < params.length; i++) {
    const pair = params[i].split('=')
    if (decodeURIComponent(pair[0]) === param)
      return decodeURIComponent(pair[1] || '')
  }
  return null
}
const NormalForm = () => {
  const { locale } = useContext(I18NContext)
  const router = useRouter()
  // const code = getQueryParam('code')
  const searchParams = useSearchParams()
  const code = searchParams.get('code')
  console.log('testsch', code)
  useEffect(() => {
    // 不带code就跳转到登录页面
    if (!code || code.trim() === '' || code === 'null' || code === 'undefined') {
      router.replace('/signin')
      return
    }

    const loginData: Record<string, any> = {
      language: locale,
      remember_me: true,
    }
    const handleTokenLogin = async () => {
      return login({
        url: `/token-login?token=${code}`,
        body: loginData,
      })
    }
    handleTokenLogin().then((res) => {
      if (res.result === 'success') {
        localStorage.setItem('console_token', res.data.access_token)
        localStorage.setItem('refresh_token', res.data.refresh_token)
        router.replace('/apps')
      }
      else {
        Toast.notify({
          type: 'error',
          message: res.data,
        })
      }
    }, (reason) => {
      localStorage.removeItem('console_token')
      localStorage.removeItem('refresh_token')
      router.replace('/signin')
    })
  }, [router])

  return (
    <>
    </>
  )
}

export default NormalForm
